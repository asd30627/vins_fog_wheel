#!/usr/bin/env bash
# Run ONE FOG-aided VINS pass on a (hard) KAIST seq at a given grade; copy results to OUT.
# Isolated (CARLA off). NO estimator change. Reuses run_one_p1_baseline.sh GRADE override.
# Usage: run_hard_one.sh <seq> <grade> [rep]
set -uo pipefail
seq="$1"; grade="$2"; rep="${3:-0}"
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
WS=/home/ivlab3/fwvio_estimator_ws
TEMPLATE="$WS/src/kaist_player/config/urban28_pankyo_fog.yaml"
OUT=/mnt/sata4t/ivlab3_data/fwvio/results/p1_grade_hard
dst="$OUT/$seq/${grade}_rep${rep}"; mkdir -p "$dst"
echo "[hard] $seq / $grade / rep$rep  $(date +%H:%M:%S)"
t0=$(date +%s)
cd "$WS"
GRADE="$grade" USE_EXPLICIT_FIXEDEXT=1 \
  bash scripts/run_one_p1_baseline.sh "$seq" "$EXT/$seq" "$TEMPLATE" \
     "$EXT/$seq/pose/$seq/global_pose.tum" fog > "$dst/runner.log" 2>&1
rc=$?; wall=$(($(date +%s)-t0))
src="$OUT/../p1_factors/_work/fog/$seq"
cp -f "$src/vins_raw/vio.tum" "$dst/" 2>/dev/null
cp -f "$src/vins_raw/vio_loop.tum" "$dst/" 2>/dev/null
cp -rf "$src/metrics" "$dst/" 2>/dev/null
cp -f "$src/logs/vins.log" "$dst/vins.log" 2>/dev/null
cp -f "$src/logs/player.log" "$dst/player.log" 2>/dev/null
# per-keyframe reliability features (REQUIRED for reliability dataset; work dir is overwritten each run)
cp -f "$src/admission/features/reliability_features_vins.csv" "$dst/reliability_features.csv" 2>/dev/null
ate=$(grep -E "rmse" "$dst/metrics/ape_vio.txt" 2>/dev/null | head -1 | grep -oE "[0-9.]+" | tail -1)
nrow=$(wc -l < "$dst/vio.tum" 2>/dev/null || echo 0)
echo "[hard] -> rc=$rc ate=${ate:-NA} rows=$nrow wall=${wall}s  dst=$dst"
