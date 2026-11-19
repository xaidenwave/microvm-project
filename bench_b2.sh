#!/bin/bash
I8042="i8042.noaux i8042.nomux i8042.nopnp i8042.dumbkbd"
echo "tier,run,guest_init_s"
for i in $(seq 10); do
  t=$(./run_t2.sh quiet mode=dmesg 2>&1 | grep -oP '\[\s*\K[0-9.]+(?=\] Run /init)')
  echo "T2,$i,$t"
  t=$(./run_t3.sh quiet mode=dmesg $I8042 2>&1 | grep -oP '\[\s*\K[0-9.]+(?=\] Run /init)')
  echo "T3_tuned,$i,$t"
done
