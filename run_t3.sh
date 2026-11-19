#!/bin/bash
# T3: Firecracker. Usage: ./run_t3.sh [extra kernel args]
CFG=$(mktemp /tmp/fc-XXXXXX.json)
cat > "$CFG" << JSON
{ "boot-source": { "kernel_image_path": "$PWD/images/vmlinux",
    "boot_args": "console=ttyS0 reboot=k panic=-1 pci=off init=/init $*" },
  "drives": [{ "drive_id": "rootfs", "path_on_host": "$PWD/images/rootfs.ext4",
    "is_root_device": true, "is_read_only": true }],
  "machine-config": { "vcpu_count": 1, "mem_size_mib": 128 } }
JSON
./firecracker --no-api --config-file "$CFG"
rm -f "$CFG"
