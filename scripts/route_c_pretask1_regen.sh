#!/usr/bin/env bash
# Route C / PRE-TASK 1 — regenerate KAIST perfeat WITH velocity (vx_j,vy_j), fog-mode, clean provenance.
# fog mode = matches the Framework 2 deploy backbone (train/deploy consistency).
# REL_WHEEL_REFERENCE_ONLY=1 => w_* populated (hand-prior lp source); REL_PERFEAT_LOG=1 => per-feature logger.
# Usage: route_c_pretask1_regen.sh <SEQ>
set -eo pipefail
SEQ="$1"; [[ -z "$SEQ" ]] && { echo "usage: $0 <SEQ>"; exit 2; }

WS=/home/ivlab3/fwvio_estimator_ws_wheel
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
SEQROOT="$EXT/$SEQ"
GT="$SEQROOT/pose/$SEQ/global_pose.tum"
TEMPLATE="$WS/src/kaist_player/config/urban28_pankyo_fog.yaml"
OUT="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/pretask1_perfeat/$SEQ"
SCRATCH="/mnt/sata4t/ivlab3_data/fwvio/results/p1_wheel_v2/_work_wheel/fog/$SEQ"
VINS_BIN="$WS/install/vins/lib/vins/vins_node"
mkdir -p "$OUT"

BIN_MD5=$(md5sum "$VINS_BIN" 2>/dev/null | cut -d' ' -f1)
COMMIT=$(git -C "$WS" rev-parse HEAD 2>/dev/null || echo nogit)
RUN_ID="rcperfeat_${SEQ}_$(date +%Y%m%d_%H%M%S)"
echo "[PRE1] start $RUN_ID  bin_md5=$BIN_MD5  commit=$COMMIT"

export USE_EXPLICIT_FIXEDEXT=1
export REL_PERFEAT_LOG=1
export REL_WHEEL_REFERENCE_ONLY=1
export PUBLISH_WHEEL_TOPIC=1   # player端: 播 wheel encoder -> /wheel/delta (estimator端 REL_WHEEL_REFERENCE_ONLY 才有資料可建 preint)
export REL_PERFEAT_CSV_PATH="$OUT/perfeat_${SEQ}.csv"
export REL_SEQUENCE_NAME="$SEQ"
export REL_RUN_ID="$RUN_ID"

bash "$WS/scripts/run_one_p1_baseline.sh" \
  "$SEQ" "$SEQROOT" "$TEMPLATE" "$GT" fog > "$OUT/runner.log" 2>&1 \
  || { echo "[PRE1] RUNNER FAILED $RUN_ID"; tail -30 "$OUT/runner.log"; exit 1; }

cp -f "$SCRATCH/logs/proc_exe_proof.txt" "$OUT/" 2>/dev/null || true
cp -f "$SCRATCH/vins_raw/vio.tum"         "$OUT/" 2>/dev/null || true
cp -f "$SCRATCH/metrics/ape_vio.txt"      "$OUT/" 2>/dev/null || true
{
  echo "run_id=$RUN_ID"; echo "seq=$SEQ  mode=fog  REL_PERFEAT_LOG=1  REL_WHEEL_REFERENCE_ONLY=1"
  echo "vins_binary=$VINS_BIN"; echo "binary_md5=$BIN_MD5"; echo "commit=$COMMIT"
  echo "perfeat_csv=$REL_PERFEAT_CSV_PATH"; echo "timestamp=$(date -Iseconds)"
} > "$OUT/provenance.txt"

CSV="$OUT/perfeat_${SEQ}.csv"
ROWS=$(wc -l < "$CSV" 2>/dev/null || echo 0)
SZ=$(du -h "$CSV" 2>/dev/null | cut -f1)
echo "[PRE1] done $RUN_ID  perfeat_rows=$ROWS  size=$SZ"
