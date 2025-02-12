#!/bin/env python3

import sys
import json
import logging
import pathlib
import re

from lxml import etree

ENVIRONMENT_FILE="/root/ovf-env.xml"
ONBOARDING_CONFIG_FILE="/etc/128T-hardware-bootstrapper/onboarding-config.json"
UDEV_RULES_FILE="/etc/udev/rules.d/129-persistent-net.rules"
LOGFILE="/root/vmwareOvfEnvParser.log"

VMWARE_IF_LABEL_REGEX = re.compile(r'^Ethernet([0-9]+)$')
NS = {
    "oe": "http://schemas.dmtf.org/ovf/environment/1",
    "ve": "http://www.vmware.com/schema/ovfenv"
}

logger = logging.getLogger(__name__)


def string2bool(string):
    return string.lower() == "true"


def create_if_map():
    # VMWare does not provide reliable interface ordering to work around this
    # we will find the NICs and associate the interface number from the label
    # provided by VMWare (EthernetX) to the PCI address
    ifMap = {}
    for path in pathlib.Path('/sys/class/net').glob('*'):
        device_dir = path / "device"
        if device_dir.exists():
            pciAddress = device_dir.resolve().name
            label = ( device_dir / "label" ).read_text().strip()
            match = VMWARE_IF_LABEL_REGEX.match(label)
            if match:
                logger.info(f"Found interface {path.stem} with PCI Address {pciAddress} and MAC Address {(path / 'address').read_text().strip()}")
                ifMap[int(match.group(1))] = pciAddress

    return ifMap


def _get_port_type(index, num_ports):
    # Stealing the logic directly from bootstrapper
    if num_ports < 4:
        return "LAN" if index != 0 else "WAN"

    if index == 0:
        return "WAN"
    if index == num_ports - 2:
        return "HASync"
    if index == num_ports - 1:
        return "HAFabric"
    return "LAN"    


def create_device_map(static_config):
    ifMap = create_if_map()
    num_ports = len(ifMap.keys())
    ethernet = []
    for ifIndex, pciAddr in sorted(ifMap.items()):
        interface = {
            "name": f"ge-0-{ifIndex}",
            "pciAddress": f"{pciAddr}",
            "type": _get_port_type(ifIndex, num_ports),
        }

        if ifIndex == 0 and static_config:
            interface.update(static_config)

        ethernet.append(interface)

    return {"ethernet": ethernet}
                    

def get_static_config(ovf_env_tree):
    logger.info("Checking for ge-0-0 static config in OVF environment")
    static_config = {}

    staticAddressXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='staticAddress']/@oe:value", namespaces=NS)
    if staticAddressXpath:
        static_config['address'] = staticAddressXpath[0]

    staticGatewayXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='staticGateway']/@oe:value", namespaces=NS)
    if staticGatewayXpath:
        static_config['gateway'] = staticGatewayXpath[0]

    vlanXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='vlan']/@oe:value", namespaces=NS)
    if vlanXpath:
        try:
            vlanNo = int(vlanXpath[0])
            if vlanNo > 0:
                static_config['vlan'] = vlanNo
        except ValueError as err:
            logger.error(f"Invalid vlan value configured: {err}")

    return static_config


def create_persistent_interfaces(device_map):
    # Have experienced issues with VMWare changing MAC addresses. The bootstrapper
    # does this by MAC address and not PCI so attempting to fallback to PCI if the MACs
    # don't match. Could also be useful if the system is migrated.
    rules = ""
    for interface in device_map['ethernet']:
        rules += f'ACTION=="add", SUBSYSTEM=="net", KERNELS=="{interface.get("pciAddress")}", NAME:="{interface.get("name")}"\n'

    numLines = pathlib.Path(UDEV_RULES_FILE).write_text(rules)


def onboard_mist_managed(ovf_env_tree):
    logger.info("Creating onboarding-config for Mist-managed router")
    onboarding_config = {
        "mode": "mist-managed",
    }

    regCodeXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='regCode']/@oe:value", namespaces=NS)
    if regCodeXpath:
        onboarding_config['registration-code'] = regCodeXpath[0]
    else:
        logger.error("Registration code not found in OVF environment, cannot continue")
        sys.exit(1)

    routerNameXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='routerName']/@oe:value", namespaces=NS)
    if routerNameXpath:
        onboarding_config['name'] = routerNameXpath[0]

    return onboarding_config


def onboard_conductor_managed(ovf_env_tree):
    logger.info("Creating onboarding-config for Conductor-managed router")
    onboarding_config = {
        "mode": "conductor-managed",
    }

    conductor1Xpath = ovf_env_tree.xpath("//oe:Property[@oe:key='conductor1']/@oe:value", namespaces=NS)
    conductor2Xpath = ovf_env_tree.xpath("//oe:Property[@oe:key='conductor2']/@oe:value", namespaces=NS)
    conductors = conductor1Xpath + conductor2Xpath
    if len(conductors)<1:
        logger.error("No conductor addresses defined, cannot continue")
        sys.exit(1)

    onboarding_config['conductor-hosts'] = conductors

    assetNameXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='assetName']/@oe:value", namespaces=NS)
    if assetNameXpath:
        onboarding_config['name'] = assetNameXpath[0]

    return onboarding_config


def onboard_conductor(ovf_env_tree):
    logger.info("Creating onboarding-config for Conductor")
    onboarding_config = {
        "mode": "conductor",
    }

    conductorNameXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='conductorName']/@oe:value", namespaces=NS)
    if conductorNameXpath:
        onboarding_config['name'] = conductorNameXpath[0]
    else:
        logger.error("No conductor name specified, cannot continue")
        sys.exit(1)

    nodeNameXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='nodeName']/@oe:value", namespaces=NS)
    if nodeNameXpath:
        onboarding_config['node-name'] = nodeNameXpath[0]
    else:
        logger.error("No node name specified, cannot continue")
        sys.exit(1)

    artifactoryUserXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='artifactoryUser']/@oe:value", namespaces=NS)
    artifactoryPasswordXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='artifactoryPassword']/@oe:value", namespaces=NS)
    if artifactoryUserXpath and artifactoryPasswordXpath:
        onboarding_config['artifactory-user'] = artifactoryUserXpath[0]
        onboarding_config['artifactory-password'] = artifactoryPasswordXpath[0]

    # Maybe do more validation here but for now let the bootstrapper do that

    nodeIpXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='nodeIp']/@oe:value", namespaces=NS)
    if nodeIpXpath:
        onboarding_config['node-ip'] = nodeIpXpath[0]

    nodeGatewayXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='nodeGateway']/@oe:value", namespaces=NS)
    if nodeGatewayXpath:
        onboarding_config['node-gateway'] = nodeGatewayXpath[0]

    interfaceNameXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='interfaceName']/@oe:value", namespaces=NS)
    if interfaceNameXpath:
        onboarding_config['interface-name'] = interfaceNameXpath[0]

    dnsServer1Xpath = ovf_env_tree.xpath("//oe:Property[@oe:key='dnsServer1']/@oe:value", namespaces=NS)
    dnsServer2Xpath = ovf_env_tree.xpath("//oe:Property[@oe:key='dnsServer2']/@oe:value", namespaces=NS)
    dnsServers = dnsServer1Xpath + dnsServer2Xpath
    if dnsServers:
        onboarding_config['dns-servers'] = dnsServers

    clusteredXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='clustered']/@oe:value", namespaces=NS)
    if clusteredXpath:
        if string2bool(clusteredXpath[0]):
            onboarding_config['clustered'] = True

    haIpXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='haIp']/@oe:value", namespaces=NS)
    if haIpXpath:
        onboarding_config['ha-ip'] = haIpXpath[0]

    haInterfaceXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='haInterface']/@oe:value", namespaces=NS)
    if haInterfaceXpath:
        onboarding_config['ha-interface-name'] = haInterfaceXpath[0]

    haPeerNameXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='haPeerName']/@oe:value", namespaces=NS)
    if haPeerNameXpath:
        onboarding_config['ha-peer-name'] = haPeerNameXpath[0]

    learnFromHaPeerXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='learnFromHaPeer']/@oe:value", namespaces=NS)
    if learnFromHaPeerXpath:
        if string2bool(learnFromHaPeerXpath[0]):
            onboarding_config['learn-from-ha-peer'] = True

    haPeerUsernameXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='haPeerUsername']/@oe:value", namespaces=NS)
    if haPeerUsernameXpath:
        onboarding_config['ha-peer-username'] = haPeerUsernameXpath[0]

    haPeerPasswordXpath = ovf_env_tree.xpath("//oe:Property[@oe:key='haPeerPassword']/@oe:value", namespaces=NS)
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
    onboardingModeXpath = tree.xpath("//oe:Property[@oe:key='onboardingMode']/@oe:value", namespaces=NS)
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

    static_config = get_static_config(tree)
    device_map = create_device_map(static_config)
    onboarding_config["devicemap"] = device_map
    create_persistent_interfaces(device_map)

    logger.info(f"Writing onboarding config: {onboarding_config}")
    with open(ONBOARDING_CONFIG_FILE, 'w') as fh:
        json.dump(onboarding_config, fh)

    logger.info("Finished successfully")


if __name__ == '__main__':
    main()
