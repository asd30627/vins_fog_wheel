#!/usr/bin/env bash
# ALPHA SWEEP (TEST binary 7f8f13c1, NOT gate binary): smooth magnitude-dosage ramp from the safe shape-only
# point. REL_KEEP_MAGNITUDE=1 + REL_KEEP_MAG_ALPHA in {0,0.1,0.2,0.3,0.5}, R=10 clamp. net ON, held-out
# F-urban35, pb3, isolated. alpha=0 = sanity: MUST reproduce shape-only 146.925 / md5 2bad3a4f (proves the
# OFF/shape-only path is not polluted by the new code). Reports per-alpha full/span/ATE/md5/clamp%/guard%.
# RAW only -- no win/direction judgment. full=0 (truncated) = not comparable.
set -o pipefail
SEQ=urban35-seoul
WS=/home/ivlab3/fwvio_estimator_ws_wheel
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
SEQROOT="$EXT/$SEQ"; GT="$SEQROOT/pose/$SEQ/global_pose.tum"
TEMPLATE="$WS/src/kaist_player/config/urban28_pankyo_fog_pb3p0.yaml"   # pb3
SCRATCH="/mnt/sata4t/ivlab3_data/fwvio/results/p1_wheel_v2/_work_wheel/fog/$SEQ"
OUTBASE="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/covon_keepmag_alpha/$SEQ${SWEEP_TAG:+_$SWEEP_TAG}"
ONNX="/home/ivlab3/dl_reliability_ws/onnx_aplus_framei/reliability_cov_aplus_F-${SEQ}.onnx"  # held-out fold
KEEP_MAG_R="${KEEP_MAG_R:-10}"
ALPHAS=(0 0.1 0.2 0.3 0.5)
mkdir -p "$OUTBASE"
source /opt/ros/jazzy/setup.bash 2>/dev/null
source "$WS/install/setup.bash" 2>/dev/null
[[ -s "$ONNX" ]] || { echo "[A] FATAL ONNX missing: $ONNX"; exit 1; }
if docker ps --format '{{.Image}}' 2>/dev/null | grep -qi carla || pgrep -x CarlaUE4-Linux-Shipping >/dev/null 2>&1; then
  echo "[A] FATAL: CARLA running -> not isolated."; exit 9; fi
gt_last=$(awk 'END{print $1}' "$GT")
echo "[A] urban35 keep-mag ALPHA sweep  binary(TEST)=$(md5sum "$WS/install/vins/lib/vins/vins_node"|cut -d' ' -f1)  onnx=$(basename "$ONNX")  pb3 R=$KEEP_MAG_R  alphas=${ALPHAS[*]}  REL_HUBER_DELTA=${REL_HUBER_DELTA:-1.0(default)}  tag=${SWEEP_TAG:-none}  $(date -Iseconds)"

run_alpha(){  # $1=alpha
  local a="$1" tag="a${1}" OUT="$OUTBASE/alpha_${1}"; mkdir -p "$OUT"
  export USE_EXPLICIT_FIXEDEXT=1
  export REL_FEATURE_RELIABILITY=1 REL_ANISO_INFO=1 REL_USE_LEARNED_MODEL=1 REL_ONNX_PATH="$ONNX" RC_APLUS=1
  export REL_WHEEL_REFERENCE_ONLY=1 PUBLISH_WHEEL_TOPIC=1 REL_SEQUENCE_NAME="$SEQ"
  export REL_KEEP_MAGNITUDE=1 REL_KEEP_MAG_CLAMP="$KEEP_MAG_R" REL_KEEP_MAG_ALPHA="$a"
  export REL_HUBER_DELTA="${REL_HUBER_DELTA:-1.0}"   # diagnostic: visual Huber delta (1.0 = gate default)
  unset REL_WHEEL_PRELOAD REL_COV_DUMP REL_PERFEAT_LOG REL_PERFEAT_CSV_PATH
  echo "[A] >>> alpha=$a START $(date +%H:%M:%S)"
  bash "$WS/scripts/run_one_p1_baseline.sh" "$SEQ" "$SEQROOT" "$TEMPLATE" "$GT" fog > "$OUT/runner.log" 2>&1
  local rc=$?
  cp -f "$SCRATCH/vins_raw/vio.tum" "$OUT/vio.tum" 2>/dev/null || true
  cp -f "$SCRATCH/metrics/ape_vio.txt" "$OUT/ape_vio.txt" 2>/dev/null || true
  cp -f "$SCRATCH/logs/vins.log" "$OUT/vins.log" 2>/dev/null || true
  if [[ ! -s "$OUT/vio.tum" ]]; then echo "[A] alpha=$a NO vio.tum (rc=$rc) -> crash? tail:"; tail -12 "$OUT/runner.log"; return 0; fi
  local rows=$(wc -l < "$OUT/vio.tum"); local vio_last=$(awk 'END{print $1}' "$OUT/vio.tum")
  local span=$(awk 'NR==1{f=$1}END{printf "%.1f",$1-f}' "$OUT/vio.tum")
  local full=$(awk -v v="$vio_last" -v g="$gt_last" 'BEGIN{print (g>0 && v >= g-10.0)?1:0}')
  local md5=$(md5sum "$OUT/vio.tum"|cut -d' ' -f1); local ate=$(grep -iE "^\s*rmse" "$OUT/ape_vio.txt" 2>/dev/null|awk '{print $2}')
  # avg clamp trigger% and guard fallback% across keep-mag windows
  local clamp=$(awk -F'trigger=' '/keep-mag\] feats=/{split($2,x,"%"); s+=x[1]; n++} END{if(n>0) printf "%.2f%%", s/n; else print "n/a"}' "$OUT/vins.log" 2>/dev/null)
  local guard=$(awk -F'guard=' '/keep-mag\] feats=/{split($2,x,"%"); s+=x[1]; n++} END{if(n>0) printf "%.2f%%", s/n; else print "n/a"}' "$OUT/vins.log" 2>/dev/null)
  local net=$(grep -oE "net=[01]" "$OUT/vins.log" 2>/dev/null | tail -1)
  echo "[A] alpha=$a DONE rc=$rc full=$full span=${span}s rows=$rows ate=${ate:-NA} md5=$md5 clamp=$clamp guard=$guard $net (windows=$(grep -c "keep-mag\] feats=" "$OUT/vins.log" 2>/dev/null))"
}

for a in "${ALPHAS[@]}"; do run_alpha "$a"; done

echo "[A] ===== ALPHA SWEEP RAW TABLE ====="
printf "[A] %-7s %-5s %-9s %-7s %-34s %-9s %-9s\n" alpha full span rows md5 clamp guard
for a in "${ALPHAS[@]}"; do
  OUT="$OUTBASE/alpha_${a}"; tum="$OUT/vio.tum"
  if [[ -s "$tum" ]]; then
    vio_last=$(awk 'END{print $1}' "$tum"); span=$(awk 'NR==1{f=$1}END{printf "%.1f",$1-f}' "$tum"); rows=$(wc -l < "$tum")
    full=$(awk -v v="$vio_last" -v g="$gt_last" 'BEGIN{print (g>0 && v>=g-10.0)?1:0}')
    md5=$(md5sum "$tum"|cut -d' ' -f1); ate=$(grep -iE "^\s*rmse" "$OUT/ape_vio.txt" 2>/dev/null|awk '{print $2}')
    clamp=$(awk -F'trigger=' '/keep-mag\] feats=/{split($2,x,"%");s+=x[1];n++}END{if(n>0)printf "%.2f%%",s/n;else print "n/a"}' "$OUT/vins.log")
    guard=$(awk -F'guard=' '/keep-mag\] feats=/{split($2,x,"%");s+=x[1];n++}END{if(n>0)printf "%.2f%%",s/n;else print "n/a"}' "$OUT/vins.log")
    printf "[A] %-7s %-5s %-9s %-7s %-34s %-9s %-9s ATE=%s\n" "$a" "$full" "${span}s" "$rows" "$md5" "$clamp" "$guard" "${ate:-NA}"
  else
    printf "[A] %-7s %-5s (no vio.tum / crash)\n" "$a" "0"
  fi
done
echo "[A]   sanity ref: alpha=0 must reproduce shape-only 146.925 / md5 2bad3a4f"
echo "[A] done $(date -Iseconds)"
