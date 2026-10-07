#!/usr/bin/env bash
# R8-3 follow-up: repeat anchor_recovery_core diagnostics on 2 more seeds (s2, s3) to determine
# whether the oracle_cull SE(3)=906m divergence (seed 1) was a one-off or systematic.
set -o pipefail
WS=/home/ivlab3/fwvio_estimator_ws_wheel
MASKDIR=$WS/logs/phase6/r8_masks
EVO=/home/ivlab3/.local/bin/evo_ape
OUT=$WS/logs/phase6/r8_diagnostics_seeds_results.csv
LOG=$WS/logs/phase6/r8_diagnostics_seeds.log
echo "seed,recording,condition,poses,resets,loop_detected,loop_accepted,ate_se3_rmse,ate_se3_median,ate_sim3_rmse" > "$OUT"

run_one() {
  local SEED="$1" REC="$2" GT="$3" LABEL="$4" SMASK="$5"
  echo "===== $LABEL $(date +%T) =====" | tee -a "$LOG"
  bash "$WS/scripts/run_orbslam_carla_logged.sh" "$REC" "$LABEL" "$SMASK" >> "$LOG" 2>&1
  pkill -9 -f stereo-inertial 2>/dev/null; pkill -9 -f paper2_carla_stereo_player_masked 2>/dev/null
  sleep 2
  local TUM=$WS/logs/phase6/orbslam_carla_${LABEL}.tum
  local SLOG=$WS/logs/phase6/orbslam_carla_${LABEL}.log
  local poses=$(wc -l < "$TUM" 2>/dev/null || echo 0)
  local resets=$(grep -c "Reseting" "$SLOG" 2>/dev/null); resets=${resets:-0}
  local loop_det=$(grep -c "Loop detected" "$SLOG" 2>/dev/null); loop_det=${loop_det:-0}
  local loop_bad=$(grep -c "BAD LOOP" "$SLOG" 2>/dev/null); loop_bad=${loop_bad:-0}
  local loop_accepted="NA"
  if [ "$loop_det" -gt 0 ]; then
    if [ "$loop_bad" -ge "$loop_det" ]; then loop_accepted="NO"; else loop_accepted="YES"; fi
  fi
  local rmse_se3=$($EVO tum "$GT" "$TUM" -a 2>/dev/null | awk '/rmse/{print $2}')
  local med_se3=$($EVO tum "$GT" "$TUM" -a 2>/dev/null | awk '/median/{print $2}')
  local rmse_sim3=$($EVO tum "$GT" "$TUM" -as 2>/dev/null | awk '/rmse/{print $2}')
  echo "  poses=$poses resets=$resets loop=$loop_det/$loop_accepted ATE_se3=$rmse_se3 sim3=$rmse_sim3" | tee -a "$LOG"
  echo "$SEED,${REC##*/},$LABEL,$poses,$resets,$loop_det,$loop_accepted,${rmse_se3:-NA},${med_se3:-NA},${rmse_sim3:-NA}" >> "$OUT"
}

for S in s2 s3; do
  REC=/mnt/sata4t/datasets/carla_fwvio/Town02__dynamic_v3r8__runanchor_recovery_core_${S}
  GT=$WS/logs/phase6/carla_gt_r8_anchor_core_${S}.tum
  run_one "$S" "$REC" "$GT" "r8_anchor_${S}_baseline" ""
  run_one "$S" "$REC" "$GT" "r8_anchor_${S}_classprior" "$MASKDIR/stereo_mask_Town02__dynamic_v3r8__runanchor_recovery_core_${S}__class_prior.json"
  run_one "$S" "$REC" "$GT" "r8_anchor_${S}_oraclecull" "$MASKDIR/stereo_mask_Town02__dynamic_v3r8__runanchor_recovery_core_${S}__oracle_cull.json"
done

echo "===== R8-3 SEEDS DIAGNOSTICS DONE $(date +%T) =====" | tee -a "$LOG"