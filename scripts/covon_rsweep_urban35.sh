#!/usr/bin/env bash
# R-sweep (TEST binary c2f569fe, NOT gate): keep-magnitude clamp R in {2,3,5}, urban35 cov-ON pb3, 1 rep each.
# Find the transition between R=1(shape-only)=146 full and R=10=77s diverged. RAW; user judges direction.
set -o pipefail
SEQ=urban35-seoul
WS=/home/ivlab3/fwvio_estimator_ws_wheel
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
SEQROOT="$EXT/$SEQ"; GT="$SEQROOT/pose/$SEQ/global_pose.tum"
TEMPLATE="$WS/src/kaist_player/config/urban28_pankyo_fog_pb3p0.yaml"
SCRATCH="/mnt/sata4t/ivlab3_data/fwvio/results/p1_wheel_v2/_work_wheel/fog/$SEQ"
OUTBASE="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/covon_rsweep/$SEQ"
ONNX="/home/ivlab3/dl_reliability_ws/onnx_aplus_framei/reliability_cov_aplus_F-${SEQ}.onnx"
mkdir -p "$OUTBASE"
source /opt/ros/jazzy/setup.bash 2>/dev/null
source "$WS/install/setup.bash" 2>/dev/null
[[ -s "$ONNX" ]] || { echo "[RSW] FATAL ONNX missing"; exit 1; }
if docker ps --format '{{.Image}}' 2>/dev/null | grep -qi carla || pgrep -x CarlaUE4-Linux-Shipping >/dev/null 2>&1; then
  echo "[RSW] FATAL: CARLA running."; exit 9; fi
gt_last=$(awk 'END{print $1}' "$GT")
echo "[RSW] urban35 keep-mag R-sweep  binary(TEST)=$(md5sum "$WS/install/vins/lib/vins/vins_node"|cut -d' ' -f1)  pb3  $(date -Iseconds)"
echo "[RSW] reference: R=1 shape-only=146.925 full | R=10=77.4s DIVERGED | baseline=60.739 full"

for R in 2 3 5; do
  OUT="$OUTBASE/R${R}"; mkdir -p "$OUT"
  export USE_EXPLICIT_FIXEDEXT=1
  export REL_FEATURE_RELIABILITY=1 REL_ANISO_INFO=1 REL_USE_LEARNED_MODEL=1 REL_ONNX_PATH="$ONNX" RC_APLUS=1
  export REL_WHEEL_REFERENCE_ONLY=1 PUBLISH_WHEEL_TOPIC=1 REL_SEQUENCE_NAME="$SEQ"
  export REL_KEEP_MAGNITUDE=1 REL_KEEP_MAG_CLAMP="$R"
  unset REL_WHEEL_PRELOAD REL_COV_DUMP REL_PERFEAT_LOG REL_PERFEAT_CSV_PATH
  echo "[RSW] >>> R=$R START $(date +%H:%M:%S)"
  bash "$WS/scripts/run_one_p1_baseline.sh" "$SEQ" "$SEQROOT" "$TEMPLATE" "$GT" fog > "$OUT/runner.log" 2>&1
  rc=$?
  cp -f "$SCRATCH/vins_raw/vio.tum" "$OUT/vio.tum" 2>/dev/null || true
  cp -f "$SCRATCH/metrics/ape_vio.txt" "$OUT/ape_vio.txt" 2>/dev/null || true
  cp -f "$SCRATCH/logs/vins.log" "$OUT/vins.log" 2>/dev/null || true
  if [[ ! -s "$OUT/vio.tum" ]]; then echo "[RSW] R=$R NO vio.tum (rc=$rc)"; tail -10 "$OUT/runner.log"; continue; fi
  rows=$(wc -l < "$OUT/vio.tum"); vio_last=$(awk 'END{print $1}' "$OUT/vio.tum")
  span=$(awk 'NR==1{f=$1}END{printf "%.1f",$1-f}' "$OUT/vio.tum")
  full=$(awk -v v="$vio_last" -v g="$gt_last" 'BEGIN{print (g>0 && v >= g-10.0)?1:0}')
  md5=$(md5sum "$OUT/vio.tum"|cut -d' ' -f1); ate=$(grep -iE "^\s*rmse" "$OUT/ape_vio.txt" 2>/dev/null|awk '{print $2}')
  clamp=$(awk -F'trigger=' '/keep-mag\] feats=/{split($2,a,"%"); s+=a[1]; n++} END{if(n>0) printf "%.2f%%", s/n; else print "n/a"}' "$OUT/vins.log" 2>/dev/null)
  note=$([[ "$full" -eq 0 ]] && echo "<<< full=0 TRUNCATED/DIVERGED, ATE NOT comparable" || echo "full")
  echo "[RSW] R=$R DONE span=${span}s rows=${rows} full=${full} ate=${ate:-NA} md5=${md5} clamp_trigger=${clamp}  ${note}"
done
echo "[RSW] ===== sweep summary (with endpoints) ====="
echo "[RSW]   R=1  (shape-only) ate=146.925 full=1"
for R in 2 3 5; do
  f=$(awk -v g="$gt_last" 'END{print ($1>=g-10.0)?1:0}' "$OUTBASE/R${R}/vio.tum" 2>/dev/null)
  a=$(grep -iE "^\s*rmse" "$OUTBASE/R${R}/ape_vio.txt" 2>/dev/null|awk '{print $2}')
  s=$(awk 'NR==1{f=$1}END{printf "%.1f",$1-f}' "$OUTBASE/R${R}/vio.tum" 2>/dev/null)
  echo "[RSW]   R=$R  ate=${a:-NA} full=${f:-?} span=${s:-?}s"
done
echo "[RSW]   R=10 (prev) ate=118(@77s) full=0 DIVERGED"
echo "[RSW]   baseline=60.739 full=1"
echo "[RSW] done $(date -Iseconds). RAW; truncated(full=0)=ATE not comparable. No direction judgment."
