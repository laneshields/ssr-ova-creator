#!/bin/env python3

import sys
import json
import logging

from lxml import etree

ENVIRONMENT_FILE="/root/ovf-env.xml"
ONBOARDING_CONFIG_FILE="/etc/128T-hardware-bootstrapper/onboarding-config.json"
LOGFILE="/root/vmwareOvfEnvParser.log"

ns = {
    "oe": "http://schemas.dmtf.org/ovf/environment/1",
    "ve": "http://www.vmware.com/schema/ovfenv"
}

logger = logging.getLogger(__name__)


def onboard_mist_managed(ovf_env_tree):
    logger.info("Creating onboarding-config for Mist-managed router")
    onboarding_config = {
        "mode": "mist-managed",
    }

    regCodeXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='regCode']/@oe:value", namespaces=ns)
    if regCodeXpath:
        onboarding_config['registration-code'] = regCodeXpath[0]
    else:
        logger.error("Registration code not found in OVF environment, cannot continue")
        sys.exit(1)

    routerNameXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='routerName']/@oe:value", namespaces=ns)
    if routerNameXpath:
        onboarding_config['name'] = routerNameXpath[0]

    return onboarding_config


def onboard_conductor_managed(ovf_env_tree):
    logger.info("Creating onboarding-config for Conductor-managed router")
    onboarding_config = {
        "mode": "conductor-managed",
    }

    conductor1Xpath = ovf_env_tree.xpath("//oe:Property[@oe:key='conductor1']/@oe:value", namespaces=ns)
    conductor2Xpath = ovf_env_tree.xpath("//oe:Property[@oe:key='conductor2']/@oe:value", namespaces=ns)
    conductors = conductor1Xpath + conductor2Xpath
    if len(conductors)<1:
        logger.error("No conductor addresses defined, cannot continue")
        sys.exit(1)

    onboarding_config['conductor-hosts'] = conductors

    assetNameXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='assetName']/@oe:value", namespaces=ns)
    if assetNameXpath:
        onboarding_config['name'] = assetNameXpath[1]

    return onboarding_config


def onboard_conductor(ovf_env_tree):
    logger.info("Creating onboarding-config for Conductor")
    onboarding_config = {
        "mode": "conductor",
    }

    conductorNameXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='assetName']/@oe:value", namespaces=ns)
    if conductorNameXpath:
        onboarding_config['name'] = conductorNameXpath[0]
    else:
        logger.error("No conductor name specified, cannot continue")
        sys.exit(1)

    nodeNameXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='nodeName']/@oe:value", namespaces=ns)
    if nodeNameXpath:
        onboarding_config['node-name'] = nodeNameXpath[0]
    else:
        logger.error("No node name specified, cannot continue")
        sys.exit(1)

    artifactoryUserXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='artifactoryUser']/@oe:value", namespaces=ns)
    artifactoryPasswordXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='artifactoryPassword']/@oe:value", namespaces=ns)
    if artifactoryUserXpath and artifactoryPasswordXpath:
        onboarding_config['artifactory-user'] = artifactoryUserXpath[0]
        onboarding_config['artifactory-password'] = artifactoryPasswordXpath[0]

    # Maybe do more validation here but for now let the bootstrapper do that

    nodeIpXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='nodeIp']/@oe:value", namespaces=ns)
    if nodeIpXpath:
        onboarding_config['node-ip'] = nodeIpXpath[0]

    nodeGatewayXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='nodeGateway']/@oe:value", namespaces=ns)
    if nodeGatewayXpath:
        onboarding_config['node-gateway'] = nodeGatewayXpath[0]

    interfaceNameXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='interfaceName']/@oe:value", namespaces=ns)
    if interfaceNameXpath:
        onboarding_config['interface-name'] = interfaceNameXpath[0]

    dnsServer1Xpath = ovf_env_tree.xpath("//oe:Property[@oe:key='dnsServer1']/@oe:value", namespaces=ns)
    dnsServer2Xpath = ovf_env_tree.xpath("//oe:Property[@oe:key='dnsServer2']/@oe:value", namespaces=ns)
    dnsServers = dnsServer1Xpath + dnsServer2Xpath
    if dnsServers:
        onboarding_config['dns-servers'] = dnsServers

    haIpXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='haIp']/@oe:value", namespaces=ns)
    if haIpXpath:
        onboarding_config['ha-ip'] = haIpXpath[0]

    haInterfaceXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='haInterface']/@oe:value", namespaces=ns)
    if haInterfaceXpath:
        onboarding_config['ha-interface-name'] = haInterfaceXpath[0]

    haPeerNameXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='haPeerName']/@oe:value", namespaces=ns)
    if haPeerNameXpath:
        onboarding_config['ha-peer-name'] = haPeerNameXpath[0]

    learnFromHaPeerXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='learnFromHaPeer']/@oe:value", namespaces=ns)
    if learnFromHaPeerXpath:
        onboarding_config['learn-from-ha-peer'] = learnFromHaPeerXpath[0]

    haPeerUsernameXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='haPeerUsername']/@oe:value", namespaces=ns)
    if haPeerUsernameXpath:
        onboarding_config['ha-peer-username'] = haPeerUsernameXpath[0]

    haPeerPasswordXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='haPeerPassword']/@oe:value", namespaces=ns)
    if haPeerPasswordXpath:
        onboarding_config['unsafe-ha-peer-password'] = haPeerPasswordXpath[0]

    return onboarding_config


def main():
    logging.basicConfig(
        filename=LOGFILE,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger.info("Looking for OVF environment data...")

    try:
        tree = etree.parse(ENVIRONMENT_FILE)
    except OSError:
        logger.error(f"Could not read environment file {ENVIRONMENT_FILE}")
        sys.exit(1)
    except lxml.etree.XMLSyntaxError as err:
        logger.error(f"Unable to parse XML from environment file: {err}")
        sys.exit(1)

    logger.info("Loaded OVF environment data, looking for onboarding mode...")
    onboardingModeXpath = tree.xpath("//oe:Property[@oe:key='onboardingMode']/@oe:value", namespaces=ns)
    if len(onboardingModeXpath)<1:
        logger.error("Did not find a value for onboarding mode in the environment, cannot continue")
        sys.exit(1)

    onboardingMode = onboardingModeXpath[0]

    if onboardingMode == "mist-managed":
        onboarding_config = onboard_mist_managed(tree)
    elif onboardingMode == "conductor-managed":
        onboarding_config = onboard_conductor_managed(tree)
    elif onboardingMode == "conductor":
        onboarding_config = onboard_conductor(tree)
    else:
        logger.error(f"Unrecognized onboarding-mode: {onboardingMode}")
        sys.exit(1)

    logger.info(f"Writing onboarding config: {onboarding_config}")
    with open(ONBOARDING_CONFIG_FILE, 'w') as fh:
        json.dump(onboarding_config, fh)

    logger.info("Finished successfully")


if __name__ == '__main__':
    main()
