#!/usr/bin/env bash
# ORB-SLAM3 STEREO on a KITTI Tracking sequence + wrapper pose logger. No IMU (stereo mode).
#   usage: run_orbslam_kitti_stereo.sh <seq>
set -o pipefail
SEQ="${1:?seq e.g. 0000}"
KITTI=/mnt/sata4t/datasets/kitti/tracking/training
WS=/home/ivlab3/fwvio_estimator_ws_wheel
VOCAB=/home/ivlab3/orbslam_ws/src/orb-slam3-ros2/vocabulary/ORBvoc.txt
CONFIG=/home/ivlab3/orbslam_ws/src/orb-slam3-ros2/config/stereo/KITTI_tracking_color.yaml
LOGDIR=$WS/logs/phase6
export DISPLAY=:1 ROS_DOMAIN_ID=82
export ORBSLAM_TRAJ_TUM="$LOGDIR/orbslam_kitti_${SEQ}.tum"
rm -f "$ORBSLAM_TRAJ_TUM"
source /home/ivlab3/orbslam_ws/install/local_setup.bash 2>/dev/null
source /opt/ros/jazzy/setup.bash 2>/dev/null

echo "[kitti] launch stereo node seq=$SEQ"
ros2 run orbslam3 stereo "$VOCAB" "$CONFIG" false \
  --ros-args -r camera/left:=/kitti/left -r camera/right:=/kitti/right \
  > "$LOGDIR/orbslam_kitti_${SEQ}.log" 2>&1 &
SLAM=$!
sleep 6
timeout 300 python3 "$WS/scripts/kitti_tracking_stereo_player.py" --seq-dir "$KITTI" --seq "$SEQ" --rate 0.5 \
  > "$LOGDIR/player_kitti_${SEQ}.log" 2>&1
echo "[kitti] player done; SIGINT then SIGKILL"
kill -INT $SLAM 2>/dev/null; sleep 6
kill -9 $SLAM 2>/dev/null; pkill -9 -f "orbslam3 stereo" 2>/dev/null; pkill -9 -f "lib/orbslam3/stereo" 2>/dev/null
sleep 1
echo "[kitti] traj lines: $(wc -l < "$ORBSLAM_TRAJ_TUM" 2>/dev/null || echo 0)"
grep -cE "Reseting|Fail|LOST|lost" "$LOGDIR/orbslam_kitti_${SEQ}.log" 2>/dev/null | sed 's/^/[kitti] warn-lines: /'
grep -m1 -E "Map created|New Map" "$LOGDIR/orbslam_kitti_${SEQ}.log" 2>/dev/null
echo "[kitti] DONE $SEQ"