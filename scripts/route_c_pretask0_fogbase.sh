#!/usr/bin/env bash
# Route C / PRE-TASK 0 — FOG-base run with CLEAN provenance, calling the WHEEL runner DIRECTLY.
# NOT via run_p1_one.sh (that wrapper hardcodes the old frozen-fork WS = the P0 bug that invalidated p1_wheel_v2).
# Usage: route_c_pretask0_fogbase.sh <SEQ> <REP>
set -eo pipefail
SEQ="$1"; REP="$2"
[[ -z "$SEQ" || -z "$REP" ]] && { echo "usage: $0 <SEQ> <REP>"; exit 2; }

WS=/home/ivlab3/fwvio_estimator_ws_wheel
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
SEQROOT="$EXT/$SEQ"
GT="$SEQROOT/pose/$SEQ/global_pose.tum"
TEMPLATE="$WS/src/kaist_player/config/urban28_pankyo_fog.yaml"   # data-only player template (binary is wheel, enforced by runner failfast)
OUT="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/pretask0_fogbase/$SEQ/rep$REP"
SCRATCH="/mnt/sata4t/ivlab3_data/fwvio/results/p1_wheel_v2/_work_wheel/fog/$SEQ"   # runner's hardcoded scratch; we copy OUT of it
VINS_BIN="$WS/install/vins/lib/vins/vins_node"

mkdir -p "$OUT"
BIN_MD5=$(md5sum "$VINS_BIN" 2>/dev/null | cut -d' ' -f1)
COMMIT=$(git -C "$WS" rev-parse HEAD 2>/dev/null || echo nogit)
RUN_ID="fogbase_${SEQ}_rep${REP}_$(date +%Y%m%d_%H%M%S)"
echo "[PRE0] start $RUN_ID  bin_md5=$BIN_MD5  commit=$COMMIT"

USE_EXPLICIT_FIXEDEXT=1 bash "$WS/scripts/run_one_p1_baseline.sh" \
  "$SEQ" "$SEQROOT" "$TEMPLATE" "$GT" fog > "$OUT/runner.log" 2>&1 \
  || { echo "[PRE0] RUNNER FAILED $RUN_ID"; tail -30 "$OUT/runner.log"; exit 1; }

# copy artifacts out of the scratch (invalid) tree into the clean per-rep dir
cp -f  "$SCRATCH/vins_raw/vio.tum"            "$OUT/" 2>/dev/null || true
cp -f  "$SCRATCH/vins_raw/vio.csv"            "$OUT/" 2>/dev/null || true
cp -rf "$SCRATCH/metrics"                     "$OUT/" 2>/dev/null || true
cp -f  "$SCRATCH/logs/proc_exe_proof.txt"     "$OUT/" 2>/dev/null || true
cp -f  "$SCRATCH/logs/vins.log"               "$OUT/vins.log" 2>/dev/null || true

# provenance manifest (required for every rep)
{
  echo "run_id=$RUN_ID"
  echo "seq=$SEQ"
  echo "rep=$REP"
  echo "mode=fog   reliability=OFF(default FEATURE_RELIABILITY_ENABLE=0 — verify in vins.log)"
  echo "vins_binary=$VINS_BIN"
  echo "binary_md5=$BIN_MD5"
  echo "commit=$COMMIT"
  echo "gt=$GT"
  echo "template=$TEMPLATE"
  echo "scratch=$SCRATCH"
  echo "timestamp=$(date -Iseconds)"
} > "$OUT/provenance.txt"

ATE=$(grep -iE "rmse" "$OUT/metrics/ape_vio.txt" 2>/dev/null | head -1 || true)
ROWS=$(wc -l < "$OUT/vio.csv" 2>/dev/null || echo 0)
echo "[PRE0] done $RUN_ID  rows=$ROWS  ape_vio_rmse_line: ${ATE:-<none>}"
