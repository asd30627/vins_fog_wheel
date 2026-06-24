#!/usr/bin/env bash
# HAND-PRIOR control (TEST binary c2f569fe, NOT gate): same keep-mag machinery (geomean anchor + clamp R),
# but Lambda source = hand-prior Lam_hand (REL_USE_LEARNED_MODEL OFF -> ran=false -> Lam=Lam_hand), NOT the net.
# Only variable vs the net keep-mag sweep = Lambda source (net vs hand). urban35 cov-ON pb3, 1 rep per R.
# R=1 -> shape-only (keep-mag OFF, det=1 hand shape). R in {2,3,5,10} -> keep-mag ON with clamp R.
# RC_APLUS=1 kept so feature selection matches the net run. RAW; user judges direction.
set -o pipefail
SEQ=urban35-seoul
WS=/home/ivlab3/fwvio_estimator_ws_wheel
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
SEQROOT="$EXT/$SEQ"; GT="$SEQROOT/pose/$SEQ/global_pose.tum"
TEMPLATE="$WS/src/kaist_player/config/urban28_pankyo_fog_pb3p0.yaml"
SCRATCH="/mnt/sata4t/ivlab3_data/fwvio/results/p1_wheel_v2/_work_wheel/fog/$SEQ"
OUTBASE="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/covon_handprior_rsweep/$SEQ"
ONNX="/home/ivlab3/dl_reliability_ws/onnx_aplus_framei/reliability_cov_aplus_F-${SEQ}.onnx"
mkdir -p "$OUTBASE"
source /opt/ros/jazzy/setup.bash 2>/dev/null
source "$WS/install/setup.bash" 2>/dev/null
if docker ps --format '{{.Image}}' 2>/dev/null | grep -qi carla || pgrep -x CarlaUE4-Linux-Shipping >/dev/null 2>&1; then
  echo "[HP] FATAL: CARLA running."; exit 9; fi
gt_last=$(awk 'END{print $1}' "$GT")
echo "[HP] urban35 HAND-PRIOR keep-mag R-sweep (net OFF)  binary(TEST)=$(md5sum "$WS/install/vins/lib/vins/vins_node"|cut -d' ' -f1)  pb3  $(date -Iseconds)"

run_R(){  # $1=R (1 => shape-only)
  local R="$1" OUT="$OUTBASE/R${R}"; mkdir -p "$OUT"
  export USE_EXPLICIT_FIXEDEXT=1
  export REL_FEATURE_RELIABILITY=1 REL_ANISO_INFO=1 RC_APLUS=1 REL_ONNX_PATH="$ONNX"
  export REL_WHEEL_REFERENCE_ONLY=1 PUBLISH_WHEEL_TOPIC=1 REL_SEQUENCE_NAME="$SEQ"
  unset REL_USE_LEARNED_MODEL                 # <<< hand-prior Lambda (ran=false -> Lam=Lam_hand)
  unset REL_WHEEL_PRELOAD REL_COV_DUMP REL_PERFEAT_LOG REL_PERFEAT_CSV_PATH
  if [[ "$R" == "1" ]]; then unset REL_KEEP_MAGNITUDE REL_KEEP_MAG_CLAMP;          # R=1 = shape-only (det=1)
  else export REL_KEEP_MAGNITUDE=1 REL_KEEP_MAG_CLAMP="$R"; fi
  echo "[HP] >>> R=$R START $(date +%H:%M:%S)"
  bash "$WS/scripts/run_one_p1_baseline.sh" "$SEQ" "$SEQROOT" "$TEMPLATE" "$GT" fog > "$OUT/runner.log" 2>&1
  local rc=$?
  cp -f "$SCRATCH/vins_raw/vio.tum" "$OUT/vio.tum" 2>/dev/null || true
  cp -f "$SCRATCH/metrics/ape_vio.txt" "$OUT/ape_vio.txt" 2>/dev/null || true
  cp -f "$SCRATCH/logs/vins.log" "$OUT/vins.log" 2>/dev/null || true
  if [[ ! -s "$OUT/vio.tum" ]]; then echo "[HP] R=$R NO vio.tum (rc=$rc)"; tail -10 "$OUT/runner.log"; return 1; fi
  local rows=$(wc -l < "$OUT/vio.tum"); local vio_last=$(awk 'END{print $1}' "$OUT/vio.tum")
  local span=$(awk 'NR==1{f=$1}END{printf "%.1f",$1-f}' "$OUT/vio.tum")
  local full=$(awk -v v="$vio_last" -v g="$gt_last" 'BEGIN{print (g>0 && v >= g-10.0)?1:0}')
  local md5=$(md5sum "$OUT/vio.tum"|cut -d' ' -f1); local ate=$(grep -iE "^\s*rmse" "$OUT/ape_vio.txt" 2>/dev/null|awk '{print $2}')
  # confirm net really OFF (no 'net=1' inference); confirm keep-mag engaged for R>1
  local netoff=$(grep -cE "reliability-cov\] feats=.*net=1" "$OUT/vins.log" 2>/dev/null)
  local clamp=$(awk -F'trigger=' '/keep-mag\] feats=/{split($2,a,"%"); s+=a[1]; n++} END{if(n>0) printf "%.2f%%", s/n; else print "n/a(shape-only)"}' "$OUT/vins.log" 2>/dev/null)
  local note=$([[ "$full" -eq 0 ]] && echo "<<< full=0 TRUNCATED, ATE NOT comparable" || echo "full")
  echo "[HP] R=$R DONE span=${span}s rows=${rows} full=${full} ate=${ate:-NA} md5=${md5} clamp=${clamp} net1_lines=${netoff}(want 0=hand)  ${note}"
}

for R in 1 2 3 5 10; do run_R "$R"; done

echo "[HP] ===== SIDE-BY-SIDE (net keep-mag vs hand-prior keep-mag, same R) ====="
echo "[HP]   baseline pb3 = 60.739 full"
printf "[HP]   %-5s | %-22s | %-22s\n" "R" "net Lambda (full/ATE)" "hand-prior Lambda (full/ATE)"
declare -A NETF=( [1]="full/146.925" [2]="trunc2s/NA" [3]="full/138.158" [5]="full/132.020" [10]="trunc77s/NA" )
for R in 1 2 3 5 10; do
  f=$(awk -v g="$gt_last" 'END{print ($1>=g-10.0)?1:0}' "$OUTBASE/R${R}/vio.tum" 2>/dev/null)
  a=$(grep -iE "^\s*rmse" "$OUTBASE/R${R}/ape_vio.txt" 2>/dev/null|awk '{print $2}')
  s=$(awk 'NR==1{f=$1}END{printf "%.1f",$1-f}' "$OUTBASE/R${R}/vio.tum" 2>/dev/null)
  hp=$([[ "$f" == "1" ]] && echo "full/${a:-NA}" || echo "trunc${s:-?}s/NA")
  printf "[HP]   R=%-3s | %-22s | %-22s\n" "$R" "${NETF[$R]}" "$hp"
done
echo "[HP] done $(date -Iseconds). RAW; truncated(full=0)=ATE not comparable. No direction judgment."
