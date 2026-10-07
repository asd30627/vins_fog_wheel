#!/usr/bin/env bash
# ORB-SLAM3 STEREO on a KITTI Odometry sequence (image_0/image_1 grayscale) + wrapper pose logger.
# No IMU. Shared image host for SemanticKITTI. Mirrors run_orbslam_kitti_stereo.sh exactly.
#   usage: e2_run_orbslam_kitti_odometry_stereo.sh <seq_dir e.g. .../sequences/00>
set -o pipefail
SEQDIR="${1:?seq dir}"
SEQNAME=$(basename "$SEQDIR")
WS=/home/ivlab3/fwvio_estimator_ws_wheel
VOCAB=/home/ivlab3/orbslam_ws/src/orb-slam3-ros2/vocabulary/ORBvoc.txt
CONFIG=/home/ivlab3/orbslam_ws/src/orb-slam3-ros2/config/stereo/KITTI_odometry_gray.yaml
LOGDIR=$WS/logs/phase6
mkdir -p "$LOGDIR"
export DISPLAY=:1 ROS_DOMAIN_ID=84
export ORBSLAM_TRAJ_TUM="$LOGDIR/orbslam_kittiodom_${SEQNAME}.tum"
rm -f "$ORBSLAM_TRAJ_TUM"
source /home/ivlab3/orbslam_ws/install/local_setup.bash 2>/dev/null
source /opt/ros/jazzy/setup.bash 2>/dev/null

echo "[kittiodom] launch stereo node seq=$SEQNAME"
ros2 run orbslam3 stereo "$VOCAB" "$CONFIG" false \
  --ros-args -r camera/left:=/kittiodom/left -r camera/right:=/kittiodom/right \
  > "$LOGDIR/orbslam_kittiodom_${SEQNAME}.log" 2>&1 &
SLAM=$!
sleep 6
timeout 300 python3 "$WS/scripts/e2_kitti_odometry_stereo_player.py" --seq-dir "$SEQDIR" --rate 0.5 \
  > "$LOGDIR/player_kittiodom_${SEQNAME}.log" 2>&1
echo "[kittiodom] player done; SIGINT then SIGKILL"
kill -INT $SLAM 2>/dev/null; sleep 6
kill -9 $SLAM 2>/dev/null; pkill -9 -f "orbslam3 stereo" 2>/dev/null; pkill -9 -f "lib/orbslam3/stereo" 2>/dev/null
sleep 1
echo "[kittiodom] traj lines: $(wc -l < "$ORBSLAM_TRAJ_TUM" 2>/dev/null || echo 0)"
grep -cE "Reseting|Fail|LOST|lost" "$LOGDIR/orbslam_kittiodom_${SEQNAME}.log" 2>/dev/null | sed 's/^/[kittiodom] warn-lines: /'
grep -m1 -E "Map created|New Map" "$LOGDIR/orbslam_kittiodom_${SEQNAME}.log" 2>/dev/null
echo "[kittiodom] DONE $SEQNAME"
