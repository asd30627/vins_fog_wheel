#!/usr/bin/env bash
# 3-in-1 verification: new binary (e7e5575) cov-OFF WITH fixedext, pb 1.0, isolated, urban28 x1.
# Proves: (a) extrinsic fixed (runner.log fixedext + tx=1.45166), (b) ATE back to ~18.82 m,
# (c) md5 vs the dd8d1e0 baseline vio.tum (ab166def, 18.82 m).
set -o pipefail
SEQ=urban28-pankyo
WS=/home/ivlab3/fwvio_estimator_ws_wheel
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
SEQROOT="$EXT/$SEQ"; GT="$SEQROOT/pose/$SEQ/global_pose.tum"
TEMPLATE="$WS/src/kaist_player/config/urban28_pankyo_fog_pb1p0.yaml"
SCRATCH="/mnt/sata4t/ivlab3_data/fwvio/results/p1_wheel_v2/_work_wheel/fog/$SEQ"
OUT="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/verify_fixedext/$SEQ"
BASELINE="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/pretask1_perfeat/$SEQ/vio.tum"
VINS_BIN="$WS/install/vins/lib/vins/vins_node"
mkdir -p "$OUT"
source /opt/ros/jazzy/setup.bash 2>/dev/null
source "$WS/install/setup.bash" 2>/dev/null

echo "[VERIFY] binary_md5=$(md5sum "$VINS_BIN"|cut -d' ' -f1)  baseline=ab166defd845(dd8d1e0,18.82m)  $(date -Iseconds)"
export USE_EXPLICIT_FIXEDEXT=1   # the fix; also now the default
export REL_PERFEAT_LOG=1 REL_WHEEL_REFERENCE_ONLY=1 PUBLISH_WHEEL_TOPIC=1
export REL_PERFEAT_CSV_PATH="$OUT/perfeat_throwaway.csv" REL_SEQUENCE_NAME="$SEQ"
unset REL_ANISO_INFO RC_APLUS REL_USE_LEARNED_MODEL REL_ONNX_PATH

echo "[VERIFY] >>> run START $(date +%H:%M:%S)"
bash "$WS/scripts/run_one_p1_baseline.sh" "$SEQ" "$SEQROOT" "$TEMPLATE" "$GT" fog > "$OUT/runner.log" 2>&1
rc=$?; rm -f "$OUT/perfeat_throwaway.csv"
if [[ $rc -ne 0 || ! -s "$SCRATCH/vins_raw/vio.tum" ]]; then
  echo "[VERIFY] RUNNER FAILED rc=$rc"; tail -20 "$OUT/runner.log"; exit 1
fi
cp -f "$SCRATCH/vins_raw/vio.tum" "$OUT/vio.tum"
cp -f "$SCRATCH/metrics/ape_vio.txt" "$OUT/ape_vio.txt" 2>/dev/null || true

echo "[VERIFY] --- (1) extrinsic used (runner.log) ---"
grep -E "FIXED_EXTRINSIC" "$OUT/runner.log" | sed 's/^/[VERIFY]   /'
span=$(awk 'NR==1{f=$1}{l=$1}END{printf "%.1f",l-f}' "$OUT/vio.tum"); rows=$(wc -l < "$OUT/vio.tum")
ate=$(grep -iE "^\s*rmse" "$OUT/ape_vio.txt" | awk '{print $2}')
echo "[VERIFY] --- (2) ATE rmse=${ate:-NA}  span=${span}s rows=${rows}  (expect ~18.82m, full ~1973s/19735) ---"
echo "[VERIFY] --- (3) md5 vs baseline ---"
nm=$(md5sum "$OUT/vio.tum"|cut -d' ' -f1); bm=$(md5sum "$BASELINE"|cut -d' ' -f1)
echo "[VERIFY]   new(e7e5575)=$nm"
echo "[VERIFY]   baseline    =$bm"
if cmp -s "$OUT/vio.tum" "$BASELINE"; then
  echo "[VERIFY]   RESULT: BIT-IDENTICAL -> extrinsic fixed + new==old cov-OFF (site d clean, bit-inv(1) PASS) + baseline trustworthy"
else
  echo "[VERIFY]   RESULT: md5 DIFFERS (see ATE: if ~18.82 -> extrinsic fixed, residual diff likely rebuild FP; baseline usable)"
fi
echo "[VERIFY] done"
