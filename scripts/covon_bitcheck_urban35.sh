#!/usr/bin/env bash
# Phase 2 PRE-CHECK (highest priority, before any ATE): is cov-ON itself run-to-run bit-identical?
# cov-ON adds an ONNX inference step over baseline; its determinism was never verified.
# Pick urban35 (most-dynamic trio seq, also short). Run cov-ON pb3 N=3 -> check vio.tum md5 equal.
#   all md5 equal  -> cov-ON deterministic, proceed.
#   md5 differ     -> STOP/report: ONNX-runtime nondeterminism (worse than the speed issue).
# cov-ON = baseline env + DL cov ONLY (held-out fold ONNX). NO REL_COV_DUMP (parity-only). No C2.
# Same isolation basis: gate binary 15a57897, wheel topic ON, factor OFF, fixedext, CARLA off, pb3.
set -o pipefail
SEQ=urban35-seoul
WS=/home/ivlab3/fwvio_estimator_ws_wheel
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
SEQROOT="$EXT/$SEQ"; GT="$SEQROOT/pose/$SEQ/global_pose.tum"
TEMPLATE="$WS/src/kaist_player/config/urban28_pankyo_fog_pb3p0.yaml"   # pb3; harness substitutes seq placeholders
SCRATCH="/mnt/sata4t/ivlab3_data/fwvio/results/p1_wheel_v2/_work_wheel/fog/$SEQ"
OUTBASE="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/covon_bitcheck/$SEQ"
ONNX="/home/ivlab3/dl_reliability_ws/onnx_aplus_framei/reliability_cov_aplus_F-${SEQ}.onnx"  # held-out fold (excludes urban35)
mkdir -p "$OUTBASE"
source /opt/ros/jazzy/setup.bash 2>/dev/null
source "$WS/install/setup.bash" 2>/dev/null
[[ -s "$ONNX" ]] || { echo "[BITCHK] FATAL ONNX missing: $ONNX"; exit 1; }
if docker ps --format '{{.Image}}' 2>/dev/null | grep -qi carla || pgrep -x CarlaUE4-Linux-Shipping >/dev/null 2>&1; then
  echo "[BITCHK] FATAL: CARLA running -> not isolated."; exit 9; fi
gt_last=$(awk 'END{print $1}' "$GT")
echo "[BITCHK] cov-ON bit-identical check  binary=$(md5sum "$WS/install/vins/lib/vins/vins_node"|cut -d' ' -f1)  onnx=$(basename "$ONNX")($(md5sum "$ONNX"|cut -c1-8))  pb3 held-out fold  $(date -Iseconds)"

for i in 1 2 3; do
  OUT="$OUTBASE/rep${i}"; mkdir -p "$OUT"
  export USE_EXPLICIT_FIXEDEXT=1
  export REL_FEATURE_RELIABILITY=1 REL_ANISO_INFO=1 REL_USE_LEARNED_MODEL=1 REL_ONNX_PATH="$ONNX" RC_APLUS=1
  export REL_WHEEL_REFERENCE_ONLY=1 PUBLISH_WHEEL_TOPIC=1 REL_SEQUENCE_NAME="$SEQ"
  unset REL_WHEEL_PRELOAD REL_COV_DUMP REL_PERFEAT_LOG REL_PERFEAT_CSV_PATH   # no C2, no parity dump
  echo "[BITCHK] >>> rep${i} (cov-ON pb3) START $(date +%H:%M:%S)"
  bash "$WS/scripts/run_one_p1_baseline.sh" "$SEQ" "$SEQROOT" "$TEMPLATE" "$GT" fog > "$OUT/runner.log" 2>&1
  rc=$?
  cp -f "$SCRATCH/vins_raw/vio.tum" "$OUT/vio.tum" 2>/dev/null || true
  cp -f "$SCRATCH/metrics/ape_vio.txt" "$OUT/ape_vio.txt" 2>/dev/null || true
  cp -f "$SCRATCH/logs/vins.log" "$OUT/vins.log" 2>/dev/null || true
  if [[ ! -s "$OUT/vio.tum" ]]; then echo "[BITCHK] rep${i} NO vio.tum (rc=$rc) -> cov-ON crash? tail:"; tail -15 "$OUT/runner.log"; exit 1; fi
  rows=$(wc -l < "$OUT/vio.tum"); vio_last=$(awk 'END{print $1}' "$OUT/vio.tum")
  span=$(awk 'NR==1{f=$1}END{printf "%.1f",$1-f}' "$OUT/vio.tum")
  full=$(awk -v v="$vio_last" -v g="$gt_last" 'BEGIN{print (g>0 && v >= g-10.0)?1:0}')
  md5=$(md5sum "$OUT/vio.tum"|cut -d' ' -f1); ate=$(grep -iE "^\s*rmse" "$OUT/ape_vio.txt" 2>/dev/null|awk '{print $2}')
  covon=$(grep -cE "reliability-cov\] feats=|reliability-cov\] ONNX ready" "$OUT/vins.log" 2>/dev/null)
  echo "[BITCHK] rep${i} (cov-ON pb3) DONE rc=$rc span=${span}s rows=${rows} full=${full} md5=${md5} ate=${ate:-NA} covon_loglines=${covon}"
done

echo "[BITCHK] ===== md5 consistency ====="
M=(); for i in 1 2 3; do M+=("$(md5sum "$OUTBASE/rep${i}/vio.tum"|cut -d' ' -f1)"); done
echo "[BITCHK]   rep1=${M[0]}"; echo "[BITCHK]   rep2=${M[1]}"; echo "[BITCHK]   rep3=${M[2]}"
if [[ "${M[0]}" == "${M[1]}" && "${M[1]}" == "${M[2]}" ]]; then
  echo "[BITCHK]   RESULT: 3/3 BIT-IDENTICAL -> cov-ON is deterministic (ONNX inference adds no nondeterminism). RAW; user judges next."
else
  echo "[BITCHK]   RESULT: NOT bit-identical -> ONNX-runtime nondeterminism. STOP and report (do NOT proceed to gate)."
fi
echo "[BITCHK] done $(date -Iseconds)"
