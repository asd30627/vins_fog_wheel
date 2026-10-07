#!/usr/bin/env bash
# ORB-SLAM3 stereo-inertial across CARLA towns (one recording per town). Uses the built pipeline:
# CARLA_640_stereo_imu.yaml + wrapper pose logger + phase6_carla_gt_to_tum.py + evo ATE.
set -o pipefail
WS=/home/ivlab3/fwvio_estimator_ws_wheel
BASE=/mnt/sata4t/datasets/carla_fwvio
EVO=/home/ivlab3/.local/bin/evo_ape
OUT=$WS/logs/phase6/phase6_orbslam3_towns_b02.csv
LOG=$WS/logs/phase6/orbslam_towns_batch.log
echo "town,recording,frames,orbslam3_rmse_m,orbslam3_median_m,poses,viba2,resets" > "$OUT"
cd "$WS"
# Re-run only the baseline-0.2 recordings with the auto-picked b02 config (config-mismatch fix).
# Town01/06 (b1, 0.5) already done; Town07 (0.5) already done with correct config.
RECS=(
 "Town02:Town02__dynamic_v3r7__rundense_near_r7_core"
 "Town04:Town04__dynamic_v3r7__rundense_near_r7_preview"
 "Town05:Town05__dynamic_v3r7__rundense_slow_r7_core"
 "Town10HD:Town10HD__dynamic_v3r7__rundense_slow_r7_core"
)
for pair in "${RECS[@]}"; do
  town="${pair%%:*}"; rec="${pair#*:}"; lbl="towns_${town}"
  echo "===== $town $rec $(date +%T) =====" | tee -a "$LOG"
  gt="$WS/logs/phase6/carla_gt_${town}.tum"
  python3 "$WS/scripts/phase6_carla_gt_to_tum.py" --rec "$BASE/$rec" --out "$gt" >> "$LOG" 2>&1
  bash "$WS/scripts/run_orbslam_carla_logged.sh" "$BASE/$rec" "$lbl" >> "$LOG" 2>&1
  pkill -9 -f stereo-inertial 2>/dev/null; sleep 2
  tum="$WS/logs/phase6/orbslam_carla_${lbl}.tum"
  frames=$(ls "$BASE/$rec/stereo_left/"*.png 2>/dev/null | wc -l)
  poses=$(wc -l < "$tum" 2>/dev/null || echo 0)
  viba=$(grep -c "end VIBA 2" "$WS/logs/phase6/orbslam_carla_${lbl}.log" 2>/dev/null)
  resets=$(grep -c "Reseting" "$WS/logs/phase6/orbslam_carla_${lbl}.log" 2>/dev/null)
  rmse=$($EVO tum "$gt" "$tum" -a 2>/dev/null | awk '/rmse/{print $2}')
  med=$($EVO tum "$gt" "$tum" -a 2>/dev/null | awk '/median/{print $2}')
  echo "$town,$rec,$frames,${rmse:-NA},${med:-NA},$poses,$viba,$resets" | tee -a "$OUT"
done
echo "===== TOWNS BATCH DONE $(date +%T) =====" | tee -a "$LOG"