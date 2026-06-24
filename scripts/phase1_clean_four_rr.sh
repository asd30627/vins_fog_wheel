#!/usr/bin/env bash
# Phase 1 clean-four baseline -- HORIZONTAL round-robin (one rep per seq per round, 3 rounds).
# Order per round: urban29 -> urban26 -> urban27 -> urban28 (short->long; 29 rep1 first).
# urban28 already has rep1 (full, ATE 17.555) -> it resumes at rep2 (OFFSET=1). Others start rep1.
# Same basis as trio: gate binary 15a57897, wheel topic ON, wheel factor OFF, DL cov OFF,
# callback (no C2), fixedext, pb1.0, CARLA off. Per-seq GT-length full check. RAW only, no judgment.
# Uses phase1_baseline.sh REP_START=idx NREP=idx -> runs exactly one rep (idx); table over reps 1..idx.
set -o pipefail
WS=/home/ivlab3/fwvio_estimator_ws_wheel
declare -A OFF=( [urban29-pankyo]=0 [urban26-dongtan]=0 [urban27-dongtan]=0 [urban28-pankyo]=1 )
SEQS=(urban29-pankyo urban26-dongtan urban27-dongtan urban28-pankyo)
echo "[RR] ===== clean-four horizontal round-robin START $(date -Iseconds) ====="
for round in 1 2 3; do
  echo "[RR] ################# ROUND $round #################"
  for SEQ in "${SEQS[@]}"; do
    idx=$(( round + ${OFF[$SEQ]} ))
    echo "[RR] --- round $round : $SEQ rep${idx} ($(date +%H:%M:%S)) ---"
    REP_START="$idx" bash "$WS/scripts/phase1_baseline.sh" "$SEQ" "$idx" \
      || { echo "[RR] $SEQ rep${idx} FAILED -> STOP"; exit 1; }
  done
done
echo "[RR] ===== all 3 rounds done $(date -Iseconds) ====="
