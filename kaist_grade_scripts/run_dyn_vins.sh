#!/usr/bin/env bash
# Run VINS (IMU-VIO) on a carla_fwvio dynamic recording to get real ego-motion vs GT.
# Forces system python3 (conda carla cv_bridge is numpy-broken) + imu_synth.csv (100Hz) + R3 config + mt0.
# Usage: bash run_dyn_vins.sh <rec_dir> <tag> [rate]
set -o pipefail
REC="${1:?rec}"; TAG="${2:?tag}"; RATE="${3:-0.2}"
WS=/home/ivlab3/fwvio_estimator_ws_wheel
CFG=$WS/src/VINS-Fusion-ROS2-jazzy/config/carla/carla_stereo_imu_1280_R3.yaml
OUT=/mnt/sata4t/ivlab3_data/fwvio/results/carla_vins/$TAG; mkdir -p "$OUT"
TMP="$OUT/config.yaml"; sed "s#^output_path:.*#output_path: \"$OUT/\"#" "$CFG" > "$TMP"
cp -f "$(dirname "$CFG")"/cam0_pinhole_1280.yaml "$(dirname "$CFG")"/cam1_pinhole_1280.yaml "$OUT/" 2>/dev/null
source /opt/ros/jazzy/setup.bash 2>/dev/null; source "$WS/install/setup.bash" 2>/dev/null
VINS=$WS/install/vins/lib/vins/vins_node
rm -f "$OUT/vio.csv"
echo "[dyn-vins] tag=$TAG rec=$REC rate=$RATE cfg=R3 imu=imu_synth.csv" | tee "$OUT/run_header.txt"
"$VINS" "$TMP" --ros-args > "$OUT/vins.log" 2>&1 &
VPID=$!; sleep 8
python3 /home/ivlab3/fwvio_ws/scripts/carla_stereo_player.py \
    --rec "$REC" --rate "$RATE" --imu --imu-csv imu_synth.csv --encoding mono8 \
    > "$OUT/player.log" 2>&1
sleep 5; kill "$VPID" 2>/dev/null; sleep 2; kill -9 "$VPID" 2>/dev/null
rows=$(wc -l < "$OUT/vio.csv" 2>/dev/null || echo 0)
echo "[dyn-vins] DONE tag=$TAG vio_rows=$rows -> $OUT" | tee -a "$OUT/run_header.txt"
grep -iE 'bias|diverg|nan|fail|crash|terminate|core' "$OUT/vins.log" 2>/dev/null | tail -3