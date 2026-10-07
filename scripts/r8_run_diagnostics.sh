#!/usr/bin/env bash
# R8-3 diagnostics: baseline / class_prior / oracle_cull ORB-SLAM3 runs on the 2 core recordings.
set -o pipefail
WS=/home/ivlab3/fwvio_estimator_ws_wheel
MASKDIR=$WS/logs/phase6/r8_masks
EVO=/home/ivlab3/.local/bin/evo_ape
OUT=$WS/logs/phase6/r8_diagnostics_results.csv
LOG=$WS/logs/phase6/r8_diagnostics.log
echo "recording,condition,poses,resets,loop_detected,loop_accepted,ate_se3_rmse,ate_se3_median,ate_sim3_rmse" > "$OUT"

run_one() {
  local REC="$1" GT="$2" LABEL="$3" SMASK="$4"
  echo "===== $LABEL $(date +%T) =====" | tee -a "$LOG"
  bash "$WS/scripts/run_orbslam_carla_logged.sh" "$REC" "$LABEL" "$SMASK" >> "$LOG" 2>&1
  pkill -9 -f stereo-inertial 2>/dev/null; pkill -9 -f paper2_carla_stereo_player_masked 2>/dev/null
  sleep 2
  local TUM=$WS/logs/phase6/orbslam_carla_${LABEL}.tum
  local SLOG=$WS/logs/phase6/orbslam_carla_${LABEL}.log
  local poses=$(wc -l < "$TUM" 2>/dev/null || echo 0)
  local resets
  resets=$(grep -c "Reseting" "$SLOG" 2>/dev/null || true)
  resets=${resets:-0}

  local loop_det
  loop_det=$(grep -c "Loop detected" "$SLOG" 2>/dev/null || true)
  loop_det=${loop_det:-0}

  local loop_bad
  loop_bad=$(grep -c "BAD LOOP" "$SLOG" 2>/dev/null || true)
  loop_bad=${loop_bad:-0}
  local loop_accepted="NA"
  if [ "$loop_det" -gt 0 ]; then
    if [ "$loop_bad" -ge "$loop_det" ]; then loop_accepted="NO"; else loop_accepted="YES"; fi
  fi
  local rmse_se3=$($EVO tum "$GT" "$TUM" -a 2>/dev/null | awk '/rmse/{print $2}')
  local med_se3=$($EVO tum "$GT" "$TUM" -a 2>/dev/null | awk '/median/{print $2}')
  local rmse_sim3=$($EVO tum "$GT" "$TUM" -as 2>/dev/null | awk '/rmse/{print $2}')
  echo "$LABEL,$poses,$resets,$loop_det,$loop_accepted,${rmse_se3:-NA},${med_se3:-NA},${rmse_sim3:-NA}" | tee -a "$LOG"
  echo "${REC##*/},$LABEL,$poses,$resets,$loop_det,$loop_accepted,${rmse_se3:-NA},${med_se3:-NA},${rmse_sim3:-NA}" >> "$OUT"
}

REC_A=/mnt/sata4t/datasets/carla_fwvio/Town02__dynamic_v3r8__runanchor_recovery_core
GT_A=$WS/logs/phase6/carla_gt_r8_anchor_core.tum
run_one "$REC_A" "$GT_A" "r8_anchor_baseline" ""
run_one "$REC_A" "$GT_A" "r8_anchor_classprior" "$MASKDIR/stereo_mask_Town02__dynamic_v3r8__runanchor_recovery_core__class_prior.json"
run_one "$REC_A" "$GT_A" "r8_anchor_oraclecull" "$MASKDIR/stereo_mask_Town02__dynamic_v3r8__runanchor_recovery_core__oracle_cull.json"

REC_D=/mnt/sata4t/datasets/carla_fwvio/Town02__dynamic_v3r8__rundynamic_noise_core
GT_D=$WS/logs/phase6/carla_gt_r8_dynnoise_core.tum
run_one "$REC_D" "$GT_D" "r8_dynnoise_baseline" ""
run_one "$REC_D" "$GT_D" "r8_dynnoise_classprior" "$MASKDIR/stereo_mask_Town02__dynamic_v3r8__rundynamic_noise_core__class_prior.json"
run_one "$REC_D" "$GT_D" "r8_dynnoise_oraclecull" "$MASKDIR/stereo_mask_Town02__dynamic_v3r8__rundynamic_noise_core__oracle_cull.json"

echo "===== R8-3 DIAGNOSTICS DONE $(date +%T) =====" | tee -a "$LOG"