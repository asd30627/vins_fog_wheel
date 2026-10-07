#!/usr/bin/env bash
# ORB-SLAM3 CARLA PV-mask comparison (repair Task C). One session, 5 variants, STEREO-consistent masks.
# baseline (L0) | all_dynamic (L1) | raw_speed | tcsvm (learned PV, L2) | oracle. ATE vs CARLA GT.
set -o pipefail
WS=/home/ivlab3/fwvio_estimator_ws_wheel
RUN=/mnt/sata4t/datasets/carla_fwvio/Town01__dynamic_v3__rundense_b1
GT=$WS/logs/phase6/carla_gt_dense_raw.tum
EVO=/home/ivlab3/.local/bin/evo_ape
cd "$WS"
declare -A M=(
  [baseline]=""
  [all_dynamic]="$WS/logs/phase6/stereo_mask_dense_all_dynamic.json"
  [raw_speed]="$WS/logs/phase6/stereo_mask_dense_validity_aware.json"
  [tcsvm]="$WS/logs/phase6/stereo_mask_dense_tcsvm.json"
  [oracle]="$WS/logs/phase6/stereo_mask_dense_oracle.json"
)
OUT=$WS/logs/phase6/carla_pv_compare.txt
: > "$OUT"
for v in baseline all_dynamic raw_speed tcsvm oracle; do
  echo "===== variant=$v $(date +%T) =====" | tee -a "$OUT"
  bash "$WS/scripts/run_orbslam_carla_logged.sh" "$RUN" "pv_${v}" "${M[$v]}" > "$WS/logs/phase6/run_carla_pv_${v}.log" 2>&1
  pkill -9 -f stereo-inertial 2>/dev/null; sleep 2
  TUM=$WS/logs/phase6/orbslam_carla_pv_${v}.tum
  lines=$(wc -l < "$TUM" 2>/dev/null || echo 0)
  resets=$(grep -c "Reseting" "$WS/logs/phase6/orbslam_carla_pv_${v}.log" 2>/dev/null)
  viba=$(grep -c "end VIBA 2" "$WS/logs/phase6/orbslam_carla_pv_${v}.log" 2>/dev/null)
  ate=$($EVO tum "$GT" "$TUM" -a 2>/dev/null | grep -iE "rmse|median" | tr '\n' ' ')
  echo "  poses=$lines resets=$resets viba2=$viba  ATE: $ate" | tee -a "$OUT"
done
echo "===== PV COMPARE DONE $(date +%T) =====" | tee -a "$OUT"