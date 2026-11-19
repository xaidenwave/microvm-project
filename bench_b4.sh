#!/bin/bash
# B4: density + KSM. Usage: ./bench_b4.sh t2   or   ./bench_b4.sh t3
TIER=$1; N=20; KSM=/sys/kernel/mm/ksm
I8042="i8042.noaux i8042.nomux i8042.nopnp i8042.dumbkbd"
[ "$TIER" = t2 ] && PROC=qemu-system-x86 || PROC=firecracker
echo 2 | sudo tee $KSM/run >/dev/null; sleep 5    # stop KSM and unmerge everything
echo "== $TIER baseline (no VMs, KSM off)"; free -m
for i in $(seq $N); do
  if [ "$TIER" = t2 ]; then ./run_t2.sh quiet mode=sleep </dev/null >/dev/null 2>&1 &
  else ./run_t3.sh quiet mode=sleep $I8042 </dev/null >/dev/null 2>&1 &
  fi
  sleep 0.3
done
sleep 10
echo "== $N VMs running, KSM off"; free -m
echo "vmm_count=$(pgrep -c $PROC)"
echo "rss_total_MB=$(ps -o rss= -p $(pgrep -d, $PROC) | awk '{s+=$1} END {print s/1024}')"
echo 1000 | sudo tee $KSM/pages_to_scan >/dev/null
echo 1 | sudo tee $KSM/run >/dev/null
echo "== KSM on: ksmd CPU usage for 10 s"; pidstat -p $(pgrep -x ksmd) 1 10 | tail -1
sleep 50
echo "== $N VMs running, KSM on for 60 s"; free -m
grep . $KSM/pages_shared $KSM/pages_sharing $KSM/general_profit
for p in $(pgrep $PROC); do cat /proc/$p/ksm_merging_pages; done \
  | awk '{s+=$1; n++} END {print "avg_merged_pages_per_vmm=" s/n " (" s/n*4/1024 " MB)"}'
pkill $PROC; sleep 2
echo 2 | sudo tee $KSM/run >/dev/null; echo 100 | sudo tee $KSM/pages_to_scan >/dev/null
echo "== done, KSM stopped and unmerged"
