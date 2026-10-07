#!/usr/bin/env bash
# Phase 4.4 availability/HMI tradeoff sweep (repair Task A).
# Sweep al_loc_m over {0.20, 0.50, 0.70} (straddles the fs_loc_err threshold 0.5 -> shows HMI reappear
# as the alert limit loosens). Compare ours_baseline (OPL-only, reference) vs dual_channel_avail.
# 3 points x 2 conditions x 5 seeds = 30 episodes. Reuses the repaired phase44_batch.py via env.
set -o pipefail
WS=/home/ivlab3/fwvio_estimator_ws_wheel
cd "$WS"
for AL in 0.20 0.50 0.70; do
  TAG="al${AL/./}"
  echo "===== sweep al_loc=$AL tag=$TAG $(date +%T) ====="
  PHASE44_TAG=$TAG PHASE44_AL_LOC=$AL \
    PHASE44_CONDS=ours_baseline,dual_channel_avail PHASE44_SEEDS=0,1,2,3,4 \
    python3 "$WS/scripts/phase44_batch.py" > "$WS/logs/phase44/sweep_${TAG}.log" 2>&1
  echo "----- done $TAG (eps: $(ls "$WS/logs/phase44/episodes_${TAG}"/*.csv 2>/dev/null | wc -l)) -----"
done
echo "===== SWEEP DONE $(date +%T) ====="