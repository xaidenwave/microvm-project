#!/bin/bash
# T1: traditional VM. Usage: ./run_t1.sh images/<image>.qcow2
exec qemu-system-x86_64 -M q35 -enable-kvm -cpu host -smp 1 -m 1024 \
  -display none -serial stdio -no-reboot -snapshot -nic none \
  -drive file="$1",if=virtio
