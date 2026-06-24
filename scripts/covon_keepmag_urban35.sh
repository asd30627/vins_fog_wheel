#!/usr/bin/env bash
# MINIMAL VERIFICATION (TEST binary, NOT gate binary): does preserving the net's magnitude (REL_KEEP_MAGNITUDE=1,
# per-window geomean anchored to FOCAL/1.5 + clamp R) bring urban35 cov-ON ATE down from the shape-only 146.925?
# rep "off": flag OFF -> sanity, must reproduce shape-only 146.925 / md5 2bad3a4f (proves OFF path == 15a57897 behavior).
# rep 1..3 : flag ON -> keep-magnitude ATE + md5 (bit-identical?) + clamp trigger rate (from vins.log).
# cov-ON env (held-out F-urban35), pb3, isolated. Uses whatever vins_node is installed (TEST binary now).
set -o pipefail
SEQ=urban35-seoul
WS=/home/ivlab3/fwvio_estimator_ws_wheel
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
SEQROOT="$EXT/$SEQ"; GT="$SEQROOT/pose/$SEQ/global_pose.tum"
TEMPLATE="$WS/src/kaist_player/config/urban28_pankyo_fog_pb3p0.yaml"   # pb3
SCRATCH="/mnt/sata4t/ivlab3_data/fwvio/results/p1_wheel_v2/_work_wheel/fog/$SEQ"
OUTBASE="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/covon_keepmag/$SEQ"
ONNX="/home/ivlab3/dl_reliability_ws/onnx_aplus_framei/reliability_cov_aplus_F-${SEQ}.onnx"  # held-out fold
KEEP_MAG_R="${KEEP_MAG_R:-10}"
mkdir -p "$OUTBASE"
source /opt/ros/jazzy/setup.bash 2>/dev/null
source "$WS/install/setup.bash" 2>/dev/null
[[ -s "$ONNX" ]] || { echo "[KM] FATAL ONNX missing: $ONNX"; exit 1; }
if docker ps --format '{{.Image}}' 2>/dev/null | grep -qi carla || pgrep -x CarlaUE4-Linux-Shipping >/dev/null 2>&1; then
  echo "[KM] FATAL: CARLA running -> not isolated."; exit 9; fi
gt_last=$(awk 'END{print $1}' "$GT")
echo "[KM] urban35 keep-magnitude verify  binary(TEST)=$(md5sum "$WS/install/vins/lib/vins/vins_node"|cut -d' ' -f1)  onnx=$(basename "$ONNX")  pb3 R=$KEEP_MAG_R  $(date -Iseconds)"

run_one(){  # $1=tag(off/1/2/3)  $2=keepmag(0/1)
  local tag="$1" km="$2" OUT="$OUTBASE/rep_${tag}"; mkdir -p "$OUT"
  export USE_EXPLICIT_FIXEDEXT=1
  export REL_FEATURE_RELIABILITY=1 REL_ANISO_INFO=1 REL_USE_LEARNED_MODEL=1 REL_ONNX_PATH="$ONNX" RC_APLUS=1
  export REL_WHEEL_REFERENCE_ONLY=1 PUBLISH_WHEEL_TOPIC=1 REL_SEQUENCE_NAME="$SEQ"
  unset REL_WHEEL_PRELOAD REL_COV_DUMP REL_PERFEAT_LOG REL_PERFEAT_CSV_PATH
  if [[ "$km" == "1" ]]; then export REL_KEEP_MAGNITUDE=1 REL_KEEP_MAG_CLAMP="$KEEP_MAG_R"; else unset REL_KEEP_MAGNITUDE REL_KEEP_MAG_CLAMP; fi
  echo "[KM] >>> rep_${tag} (keepmag=$km) START $(date +%H:%M:%S)"
  bash "$WS/scripts/run_one_p1_baseline.sh" "$SEQ" "$SEQROOT" "$TEMPLATE" "$GT" fog > "$OUT/runner.log" 2>&1
  local rc=$?
  cp -f "$SCRATCH/vins_raw/vio.tum" "$OUT/vio.tum" 2>/dev/null || true
  cp -f "$SCRATCH/metrics/ape_vio.txt" "$OUT/ape_vio.txt" 2>/dev/null || true
  cp -f "$SCRATCH/logs/vins.log" "$OUT/vins.log" 2>/dev/null || true
  if [[ ! -s "$OUT/vio.tum" ]]; then echo "[KM] rep_${tag} NO vio.tum (rc=$rc) -> crash? tail:"; tail -15 "$OUT/runner.log"; return 1; fi
  local rows=$(wc -l < "$OUT/vio.tum"); local vio_last=$(awk 'END{print $1}' "$OUT/vio.tum")
  local span=$(awk 'NR==1{f=$1}END{printf "%.1f",$1-f}' "$OUT/vio.tum")
  local full=$(awk -v v="$vio_last" -v g="$gt_last" 'BEGIN{print (g>0 && v >= g-10.0)?1:0}')
  local md5=$(md5sum "$OUT/vio.tum"|cut -d' ' -f1); local ate=$(grep -iE "^\s*rmse" "$OUT/ape_vio.txt" 2>/dev/null|awk '{print $2}')
  # aggregate clamp trigger rate across windows (keep-mag log lines)
  local clamp=$(awk -F'trigger=' '/keep-mag\] feats=/{split($2,a,"%"); s+=a[1]; n++} END{if(n>0) printf "%.2f%% (avg over %d windows)", s/n, n; else print "n/a"}' "$OUT/vins.log" 2>/dev/null)
  echo "[KM] rep_${tag} (keepmag=$km) DONE rc=$rc span=${span}s rows=${rows} full=${full} md5=${md5} ate=${ate:-NA} clamp_trigger=${clamp}"
}

run_one off 0          # sanity: OFF path must reproduce shape-only 146.925 / md5 2bad3a4f
run_one 1 1
run_one 2 1
run_one 3 1

echo "[KM] ===== summary ====="
echo "[KM]   urban35 pb3 baseline (existing)        = 60.739"
echo "[KM]   urban35 pb3 cov-ON shape-only (exist)  = 146.925  md5 2bad3a4f"
M=(); for t in 1 2 3; do M+=("$(md5sum "$OUTBASE/rep_${t}/vio.tum" 2>/dev/null|cut -d' ' -f1)"); done
A=$(grep -iE "^\s*rmse" "$OUTBASE/rep_1/ape_vio.txt" 2>/dev/null|awk '{print $2}')
echo "[KM]   urban35 pb3 cov-ON keep-magnitude      = ${A:-NA}  md5(rep1/2/3)=${M[0]} / ${M[1]} / ${M[2]}"
if [[ -n "${M[0]}" && "${M[0]}" == "${M[1]}" && "${M[1]}" == "${M[2]}" ]]; then echo "[KM]   keep-mag determinism: 3/3 BIT-IDENTICAL"; else echo "[KM]   keep-mag determinism: NOT bit-identical -> report"; fi
echo "[KM]   sanity (OFF rep) ate=$(grep -iE "^\s*rmse" "$OUTBASE/rep_off/ape_vio.txt" 2>/dev/null|awk '{print $2}') md5=$(md5sum "$OUTBASE/rep_off/vio.tum" 2>/dev/null|cut -d' ' -f1)  (expect 146.925 / 2bad3a4f)"
echo "[KM] done $(date -Iseconds). NOTE: baseline pb1.0 / cov-ON pb3 -> speed diff included, not pure DL. RAW, no win judgment."
