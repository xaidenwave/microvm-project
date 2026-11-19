#!/bin/bash
# T2: QEMU microvm. Usage: ./run_t2.sh [extra kernel args]
exec qemu-system-x86_64 -M microvm,pit=off,pic=off -enable-kvm -cpu host -smp 1 -m 128 \
  -nodefaults -no-user-config -display none -serial stdio -no-reboot \
  -kernel images/vmlinux \
  -append "console=ttyS0 root=/dev/vda ro init=/init reboot=t panic=-1 $*" \
  -drive id=d,file=images/rootfs.ext4,format=raw,if=none,readonly=on \
  -device virtio-blk-device,drive=d
