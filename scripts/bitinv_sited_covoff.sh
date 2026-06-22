#!/usr/bin/env bash
# site d bit-invariance check (1): cov-OFF path must stay bit-identical to dd8d1e0.
# Re-run urban28 wheel-on cov-OFF with the NEW binary, SAME env as the dd8d1e0 baseline
# (provenance binary_md5=ab166defd845, pretask1_perfeat/urban28-pankyo/vio.tum), byte-diff vio.tum.
# NO REL_ANISO_INFO / NO RC_APLUS -> computeFeatureReliabilityAnisoLearned never called -> my edits dormant.
set -eo pipefail
SEQ=urban28-pankyo
WS=/home/ivlab3/fwvio_estimator_ws_wheel
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
SEQROOT="$EXT/$SEQ"
GT="$SEQROOT/pose/$SEQ/global_pose.tum"
TEMPLATE="$WS/src/kaist_player/config/urban28_pankyo_fog.yaml"
BASELINE_TUM="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/pretask1_perfeat/$SEQ/vio.tum"
SCRATCH="/mnt/sata4t/ivlab3_data/fwvio/results/p1_wheel_v2/_work_wheel/fog/$SEQ"
BITINV="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/bitinv_sited/$SEQ"
VINS_BIN="$WS/install/vins/lib/vins/vins_node"
mkdir -p "$BITINV"

BIN_MD5=$(md5sum "$VINS_BIN" | cut -d' ' -f1)
BASE_MD5=$(md5sum "$BASELINE_TUM" | cut -d' ' -f1)
echo "[BITINV] new_binary_md5=$BIN_MD5  (baseline was ab166defd845a2866b558527b82c43fa = dd8d1e0)"
echo "[BITINV] baseline vio.tum md5=$BASE_MD5  path=$BASELINE_TUM"

# EXACT baseline env (cov-OFF): wheel-on reference-only + perfeat logging; perfeat csv to throwaway scratch.
export REL_PERFEAT_LOG=1
export REL_WHEEL_REFERENCE_ONLY=1
export PUBLISH_WHEEL_TOPIC=1
export REL_PERFEAT_CSV_PATH="$BITINV/perfeat_throwaway.csv"
export REL_SEQUENCE_NAME="$SEQ"
export REL_RUN_ID="bitinv_sited_$(date +%Y%m%d_%H%M%S)"
# explicitly DO NOT set REL_ANISO_INFO / RC_APLUS / REL_USE_LEARNED_MODEL (cov-OFF)
unset REL_ANISO_INFO RC_APLUS REL_USE_LEARNED_MODEL REL_ONNX_PATH

bash "$WS/scripts/run_one_p1_baseline.sh" "$SEQ" "$SEQROOT" "$TEMPLATE" "$GT" fog > "$BITINV/runner.log" 2>&1 \
  || { echo "[BITINV] RUNNER FAILED"; tail -30 "$BITINV/runner.log"; exit 1; }

NEW_TUM="$SCRATCH/vins_raw/vio.tum"
[[ -s "$NEW_TUM" ]] || { echo "[BITINV] new vio.tum missing/empty: $NEW_TUM"; tail -30 "$BITINV/runner.log"; exit 1; }
cp -f "$NEW_TUM" "$BITINV/vio_newbin.tum"
rm -f "$REL_PERFEAT_CSV_PATH"  # don't keep the throwaway 2GB perfeat

NEW_MD5=$(md5sum "$BITINV/vio_newbin.tum" | cut -d' ' -f1)
echo "[BITINV] new(cov-OFF) vio.tum md5=$NEW_MD5"
echo "[BITINV] baseline      vio.tum md5=$BASE_MD5"
if cmp -s "$BASELINE_TUM" "$BITINV/vio_newbin.tum"; then
  echo "[BITINV] RESULT: BIT-IDENTICAL  -> check(1) PASS (cov-OFF unchanged by site d)"
else
  echo "[BITINV] RESULT: DIFFERS  -> investigate (lines differing:)"
  diff <(head -5 "$BASELINE_TUM") <(head -5 "$BITINV/vio_newbin.tum") || true
  echo "[BITINV] total lines base=$(wc -l <"$BASELINE_TUM") new=$(wc -l <"$BITINV/vio_newbin.tum")"
fi
{ echo "new_binary_md5=$BIN_MD5"; echo "new_vio_tum_md5=$NEW_MD5"; echo "baseline_vio_tum_md5=$BASE_MD5";
  echo "baseline_binary_md5=ab166defd845a2866b558527b82c43fa (dd8d1e0)"; echo "commit=$(git -C "$WS" rev-parse HEAD)";
  echo "env=cov-OFF (fog,REL_PERFEAT_LOG=1,REL_WHEEL_REFERENCE_ONLY=1,PUBLISH_WHEEL_TOPIC=1; no ANISO/RC_APLUS)";
  echo "timestamp=$(date -Iseconds)"; } > "$BITINV/provenance.txt"
echo "[BITINV] done"
