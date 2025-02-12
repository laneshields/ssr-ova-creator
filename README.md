# SSR OVA Creator #

A tool for creating an OVA for deploying Juniper Networks Session Smart Router on VMWare platforms. When deployed the resulting OVA will provide options that can be configured through the VMWare GUI or APIs to provide data to the VM used to continue onboarding.

This tool is provided as community supported and is not maintained by Juniper Networks officially. Any issues can be reported through this github repository with no guarantee that a fix will be provided and no SLA for any fix timeframes.

## The Build Environment ##

This has been validated on an Oracle Linux 7.9 installation installed on an x86_64 server. Other OS and architecures may work but have not been tested and may require additional investigation by the user. Particularly due to the requirement to compile C code.

From a base OL7.9 installation, the environment may be prepared by running the following commands as root.
```
dnf install git gcc qemu-img
git clone https://github.com/laneshields/ssr-ova-creator.git
cd ssr-ova-creator/
```

An official SSR IBU qcow2 image should be obtained and placed in the project directory. This tool makes heavy user of the advanced onboarding workflows provided by the hardware bootstrapper. Therefore only SSR versions 6.3.0 or newer are supported.

## Creating the ISO ##

From the project directory, simply run the command `./create_ova.sh`. The tool will look for SSR qcow2 images in the current directory (if it finds more than one it will exit as it will be unsure which version to use). It will create a vfat disk image that will be detected by cloud-init as a NoCloud datasource. It will place `user-data` and `meta-data` files on this disk image that will be used to automate the process along with helper scripts. It will convert this disk image and the qcow to VMDK format. It will create an OVF file from the template and it will create a manifest file with appropriate checksums for these files. It will then create an OVA file containing the ovf, manifest, and disk images that can be readily deployed in VMWare. The OVA file will be the same name as the qcow file just with the extension .ova.

## OVA parameters ##

When deploying the OVA file, there are several perameters that can be set by the user to automate the onboarding of the SSR. These can be set through API calls, by using ovftool for a command line interface, or through the VMWare Web interface. This section shows the web interface in ESXi 6.7 along with an explanation of the parameters available in each section.

The OVF format does not provide many capabilities for input validation, so it is very easy for a user to pass through an invalid option. The help text should be referenced and certain common mistakes will be called out below.

### Network mappings ##

In the deployment options section, the user will be presented with the following secreen:
<img width="936" alt="image" src="https://github.com/user-attachments/assets/709927a3-b769-49e7-9f38-14504798dade" />

The user should use the individual drop down boxes to map the interfaces to the appropriate port groups. The VM will onboard with a devicemap setting ge-0-0 to WAN, ge-0-6 to HA sync, and ge-0-7 to HA fabric.

### Onboarding Mode ###

The Additional settings section provides further customization. This is broken into sections with the first section specifying the onboarding mode as shwon below:
<img width="936" alt="image" src="https://github.com/user-attachments/assets/8556069b-06a3-4250-b35a-9c960b38ab08" />

There is an individual section with additional options for each onboarding mode. With the exception of static addressing for ge-0-0 only the options that map to the chosen onboarding-mode will be read by the automation during boot.

### Interface ge-0-0 Static Configuration ###

This section allows you to configure a static address on the WAN port during onboarding. If you wish to use DHCP, do not set any of these options.
<img width="936" alt="image" src="https://github.com/user-attachments/assets/d1ba44c7-23c1-4dba-9567-3e5140ecee78" />

It is extremely rare to be able to see VLAN tags in VMWare, however this capability is available if needed.

> **Note:** The address configuration requires a prefix in slash format. Do not omit the prefix.

### Mist Managed Configuration ###

This section should be used when onboarding-mode is mist-managed:
<img width="936" alt="image" src="https://github.com/user-attachments/assets/81cbab82-8a66-4314-8d59-e9341cb85eb6" />

The registration-code is required for successful onboarding. The router name is optional and if omitted the system wll try to fall back to an auto-generated name using a serial number VMWare places in the VMs DMI.

### Conductor Managed Configuration ###

This section should be used when onboarding-mode is conductor-managed:
<img width="936" alt="image" src="https://github.com/user-attachments/assets/a989d784-13f0-4ceb-8732-2d85e9af5609" />

At least one address for conductor must be specified for successful onboarding. If the conductor is HA an address for each of the conductor nodes must be specified to ensure successful onboarding. The asset id is optional and if omitted the system will autogenerate an id that starts with `vmware-`.

### Conductor Configuration ###

This section should be used when onboarding-mode is conductor:
<img width="936" alt="image" src="https://github.com/user-attachments/assets/a3d5c9d5-26c6-4946-bc59-72f43430a8d6" />

This section presents the largest number of options and, unfortunately, is the least tested. Onboarding of an HA conductor from this OVA has not been tested at this time. At a minimum, the Conductor Name must be specified in order for successful onboarding.

> **Note:** To assign a static address to the management interface of the conductor, please use the options here for Node IP (address/prefix), Node Gateway, Management Interface (ge-0-x), and DNS servers instead of the ge-0-0 static configuration section

## Troubleshooting Onboarding ##

If there are issues with onboarding and the supplied scripts are suspected, please login to the VM via console and check the following:
- /root/ovf-env.xml - this should contain the VMWare guestinfo.ofenv data supplied by the VMX for the options configured during OVA deployment. This file is created by the get_environment_data application. If this output does not seem correct, the C code may need to be investigated.
- /root/vmwareOvfEnvParser.log - this logfile is generted by the parse_environment script and may show errors due to unexpected inputs.
- journalctl -u 128T-hardware-bootstrapper - Assuming the automation in this repo was successful this process will read and act upon the generated onboarding configuration. If bad data was passed in, this will likely fail and may provide some details.



