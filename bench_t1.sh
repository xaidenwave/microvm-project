#!/bin/bash
# T1: 5 boots, measuring time-to-BOOTED and total cycle time
for i in 1 2 3 4 5; do
  start=$(date +%s.%N)
  ./run_t1.sh images/fedora-bench.qcow2 2>&1 | while IFS= read -r line; do
    case "$line" in
      *BOOTED*) awk "BEGIN{printf \"run $i booted_after=%.3fs\n\", $(date +%s.%N)-$start}" ;;
      *"Startup finished"*) echo "run $i ${line//$'\r'/}" ;;
    esac
  done
  awk "BEGIN{printf \"run $i total=%.3fs\n\", $(date +%s.%N)-$start}"
done
