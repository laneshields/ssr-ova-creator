#!/bin/bash

SSRQCOWPATTERN="SSR*.qcow2"
QCOWS_FOUND=`find . -name $SSRQCOWPATTERN -printf '.' | wc -m`
if [[ $QCOWS_FOUND -lt 1 ]]; then
    echo "Did not find any SSR qcows in the current directory, exiting"
    exit 1
fi

if [[ $QCOWS_FOUND -gt 1 ]];then
    echo "Found more than one SSR qcow in the current directory, please ensure only one exists to make sure we act on the correct one"
    exit 1
fi

SSRQCOWFILE=`find . -name $SSRQCOWPATTERN -print -quit`
export SSRDISKNAME=`basename "${SSRQCOWFILE%.*}"`

echo "Working with this SSR image: ${SSRDISKNAME}"

echo "Creating disk image for cloud-init NoCloud data"
dd if=/dev/zero of=nocloud.img bs=1M count=10
mkfs.vfat -n cidata nocloud.img
mount -o loop nocloud.img /mnt

# Copy our helper scripts and nocloud user-data and meta-data onto the disk
gcc -std=c99 -o /mnt/get_environment_data get_environment_data/get_environment_data.c
cp parse_environment/parse_environment.py /mnt
cp meta-data /mnt
cp user-data /mnt
umount /mnt

echo "Converting NoCloud disk image into VMDK format"
qemu-img convert -O vmdk -o subformat=streamOptimized nocloud.img nocloud.vmdk

if [[ -f "${SSRDISKNAME}.vmdk" ]]; then
    echo "Found existing VMDK image ${SSRDISKNAME}.vmdk, not converting again"
else
    echo "Converting SSR qcow into VMDK format, this may take some time to complete..."
    qemu-img convert -O vmdk -o subformat=streamOptimized ${SSRDISKNAME}.qcow2 ${SSRDISKNAME}.vmdk
fi

echo "Creating OVF from template"
envsubst < ssr.ovf.template > ssr.ovf

echo "Creating manifest file with checksums"
echo SHA256\(ssr.ovf\)= `sha256sum ssr.ovf | awk '{print $1}'` > ssr.mf
echo SHA256\(nocloud.vmdk\)= `sha256sum nocloud.vmdk | awk '{print $1}'` >> ssr.mf
echo SHA256\(${SSRDISKNAME}.vmdk\)= `sha256sum ${SSRDISKNAME}.vmdk | awk '{print $1}'` >> ssr.mf

echo "Creating OVA package"
tar -cvf ${SSRDISKNAME}.ova ssr.ovf ssr.mf nocloud.vmdk ${SSRDISKNAME}.vmdk

echo "All done"
