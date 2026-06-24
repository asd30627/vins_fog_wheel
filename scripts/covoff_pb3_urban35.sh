#!/usr/bin/env bash
# DIAGNOSTIC: urban35 wheel-on cov-OFF baseline at pb3 (to isolate speed-effect vs DL-effect in the
# 146.92 cov-ON number). Pure baseline, NO DL cov. Same env as the clean baseline EXCEPT pb3.
# 3 numbers to compare afterwards: urban35 pb1.0 baseline 60.739 | pb3 baseline ? | pb3 cov-ON 146.924.
# Basis: gate binary 15a57897, wheel topic ON, factor OFF, DL cov OFF, callback, fixedext, CARLA off, pb3.
set -o pipefail
SEQ=urban35-seoul
WS=/home/ivlab3/fwvio_estimator_ws_wheel
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
SEQROOT="$EXT/$SEQ"; GT="$SEQROOT/pose/$SEQ/global_pose.tum"
TEMPLATE="$WS/src/kaist_player/config/urban28_pankyo_fog_pb3p0.yaml"   # pb3
SCRATCH="/mnt/sata4t/ivlab3_data/fwvio/results/p1_wheel_v2/_work_wheel/fog/$SEQ"
OUTBASE="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/covoff_pb3/$SEQ"
mkdir -p "$OUTBASE"
source /opt/ros/jazzy/setup.bash 2>/dev/null
source "$WS/install/setup.bash" 2>/dev/null
if docker ps --format '{{.Image}}' 2>/dev/null | grep -qi carla || pgrep -x CarlaUE4-Linux-Shipping >/dev/null 2>&1; then
  echo "[OFF3] FATAL: CARLA running -> not isolated."; exit 9; fi
gt_last=$(awk 'END{print $1}' "$GT")
echo "[OFF3] urban35 pb3 cov-OFF baseline  binary=$(md5sum "$WS/install/vins/lib/vins/vins_node"|cut -d' ' -f1)  pb3 DL-OFF  $(date -Iseconds)"
for i in 1 2; do
  OUT="$OUTBASE/rep${i}"; mkdir -p "$OUT"
  export USE_EXPLICIT_FIXEDEXT=1
  export REL_WHEEL_REFERENCE_ONLY=1 PUBLISH_WHEEL_TOPIC=1 REL_SEQUENCE_NAME="$SEQ"
  unset REL_ANISO_INFO RC_APLUS REL_USE_LEARNED_MODEL REL_ONNX_PATH REL_WHEEL_PRELOAD \
        REL_PERFEAT_LOG REL_COV_DUMP REL_FEATURE_RELIABILITY REL_PERFEAT_CSV_PATH
  echo "[OFF3] >>> rep${i} (cov-OFF pb3) START $(date +%H:%M:%S)"
  bash "$WS/scripts/run_one_p1_baseline.sh" "$SEQ" "$SEQROOT" "$TEMPLATE" "$GT" fog > "$OUT/runner.log" 2>&1
  rc=$?
  cp -f "$SCRATCH/vins_raw/vio.tum" "$OUT/vio.tum" 2>/dev/null || true
  cp -f "$SCRATCH/metrics/ape_vio.txt" "$OUT/ape_vio.txt" 2>/dev/null || true
  cp -f "$SCRATCH/logs/vins.log" "$OUT/vins.log" 2>/dev/null || true
  if [[ ! -s "$OUT/vio.tum" ]]; then echo "[OFF3] rep${i} NO vio.tum (rc=$rc)"; tail -12 "$OUT/runner.log"; exit 1; fi
  rows=$(wc -l < "$OUT/vio.tum"); vio_last=$(awk 'END{print $1}' "$OUT/vio.tum")
  span=$(awk 'NR==1{f=$1}END{printf "%.1f",$1-f}' "$OUT/vio.tum")
  full=$(awk -v v="$vio_last" -v g="$gt_last" 'BEGIN{print (g>0 && v >= g-10.0)?1:0}')
  md5=$(md5sum "$OUT/vio.tum"|cut -d' ' -f1); ate=$(grep -iE "^\s*rmse" "$OUT/ape_vio.txt" 2>/dev/null|awk '{print $2}')
  echo "[OFF3] rep${i} (cov-OFF pb3) DONE rc=$rc span=${span}s rows=${rows} full=${full} md5=${md5} ate=${ate:-NA}"
done
echo "[OFF3] ===== 3-way compare ====="
echo "[OFF3]   urban35 pb1.0 baseline = 60.739 (existing)"
echo "[OFF3]   urban35 pb3  baseline  = $(grep -iE "^\s*rmse" "$OUTBASE/rep1/ape_vio.txt"|awk '{print $2}') (this run)"
echo "[OFF3]   urban35 pb3  cov-ON    = 146.924786 (existing bitcheck)"
echo "[OFF3] RAW only — user judges speed-effect vs DL-effect. done $(date -Iseconds)"
