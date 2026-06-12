#!/usr/bin/env bash
# P1a wrapper: run ONE arm (fog=arm B / imu=arm A) for ONE seq, copy results to a tagged P1a dir.
# Zero estimator source change: only flips player imu_source via run_one_fixedext_baseline.sh CONFIG_MODE.
set -eo pipefail
SEQ="$1"; MODE="$2"; REP="${3:-0}"        # MODE = fog | imu
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
SEQROOT="$EXT/$SEQ"
GT="$SEQROOT/pose/$SEQ/global_pose.tum"
TEMPLATE=/home/ivlab3/fwvio_estimator_ws/src/kaist_player/config/urban28_pankyo_fog.yaml
OUT="/mnt/sata4t/ivlab3_data/fwvio/results/p1_factors/$SEQ/${MODE}_rep${REP}"
mkdir -p "$OUT"
export USE_EXPLICIT_FIXEDEXT=1
echo "[P1A] start seq=$SEQ mode=$MODE rep=$REP $(date +%H:%M:%S)"
bash /home/ivlab3/fwvio_estimator_ws/scripts/run_one_p1_baseline.sh \
     "$SEQ" "$SEQROOT" "$TEMPLATE" "$GT" "$MODE" > "$OUT/runner.log" 2>&1 || { echo "[P1A] RUNNER FAILED seq=$SEQ mode=$MODE"; tail -20 "$OUT/runner.log"; exit 1; }
SRC="/mnt/sata4t/ivlab3_data/fwvio/results/p1_factors/_work/$MODE/$SEQ"
cp -f "$SRC/vins_raw/vio.csv" "$OUT/" 2>/dev/null || true
cp -f "$SRC/vins_raw/vio.tum" "$OUT/" 2>/dev/null || true
cp -rf "$SRC/metrics" "$OUT/" 2>/dev/null || true
cp -f "$SRC/logs/vins.log" "$OUT/vins.log" 2>/dev/null || true
cp -f "$SRC/logs/player.log" "$OUT/player.log" 2>/dev/null || true
NROW=$(wc -l < "$OUT/vio.csv" 2>/dev/null || echo 0)
echo "[P1A] done seq=$SEQ mode=$MODE rep=$REP vio_rows=$NROW $(date +%H:%M:%S)"