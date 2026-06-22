#!/usr/bin/env bash
# Health watcher for the isolated determinism check. Emits one health line every ~12 min.
# ALERT (and exit) only on genuine trouble: orchestrator gone w/o "[DET] done", or VINS hung
# (vio.csv rows unchanged across 2 consecutive ticks). Phase-aware: between-runs/ML phase (no
# vins_node) and new-run file reset (rows drop) are normal, not stalls.
CSV=/mnt/sata4t/ivlab3_data/fwvio/results/p1_wheel_v2/_work_wheel/fog/urban28-pankyo/vins_raw/vio.csv
LOG=/tmp/det_check.out
prev=0; stall=0
while true; do
  sleep 720
  ts=$(date +%H:%M:%S)
  orch=$(pgrep -f det_check_wheelon | head -1)
  vins=$(pgrep -f vins_node | head -1)
  rows=$(wc -l < "$CSV" 2>/dev/null || echo 0)
  done=$(grep -c "\[DET\] done" "$LOG" 2>/dev/null)
  lastdet=$(grep "\[DET\]" "$LOG" 2>/dev/null | tail -1 | sed 's/\[DET\] //')
  if [ "${done:-0}" -ge 1 ]; then echo "HEALTH $ts: orchestrator FINISHED ([DET] done). last: $lastdet"; break; fi
  if [ -z "$orch" ]; then echo "HEALTH-ALERT $ts: orchestrator process GONE without [DET] done — likely died. last: $lastdet"; break; fi
  if [ -n "$vins" ]; then
    if [ "$rows" -gt "$prev" ]; then
      stall=0; echo "HEALTH $ts: OK vins running, vio.csv rows=$rows (+$((rows-prev)))"
    elif [ "$rows" -lt "$((prev/2))" ]; then
      stall=0; echo "HEALTH $ts: OK new run started (vio.csv reset to $rows)"
    else
      stall=$((stall+1))
      if [ "$stall" -ge 2 ]; then echo "HEALTH-ALERT $ts: vio.csv STUCK at $rows for ~24min, vins alive — VINS likely HUNG"; break
      else echo "HEALTH-WARN $ts: vio.csv rows=$rows not advancing (tick $stall/2) — watching"; fi
    fi
    prev=$rows
  else
    echo "HEALTH $ts: orchestrator alive, between-runs/ML phase (no vins_node) rows=$rows. last: $lastdet"
    prev=0
  fi
done
