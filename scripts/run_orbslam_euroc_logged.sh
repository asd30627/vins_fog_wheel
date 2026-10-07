#!/usr/bin/env bash
# Run ORB-SLAM3 stereo-inertial on EuRoC MH_01_easy with the wrapper pose logger (repair).
# Online TUM trajectory is written live; process is force-killed after the bag (no BA-hang wait).
#   usage: run_orbslam_euroc_logged.sh <label> [mask_json]
set -o pipefail
LABEL="${1:-baseline}"; MASKJSON="${2:-}"
LOGDIR=/home/ivlab3/fwvio_estimator_ws_wheel/logs/phase6
VOCAB=/home/ivlab3/orbslam_ws/src/orb-slam3-ros2/vocabulary/ORBvoc.txt
CONFIG=/home/ivlab3/orbslam_ws/src/orb-slam3-ros2/config/stereo-inertial/EuRoC.yaml
BAG=/mnt/sata4t/datasets/EuRoC_full/ros2_bags/MH_01_easy
mkdir -p "$LOGDIR"
export DISPLAY=:1 ROS_DOMAIN_ID=80
export ORBSLAM_TRAJ_TUM="$LOGDIR/orbslam_traj_${LABEL}.tum"
rm -f "$ORBSLAM_TRAJ_TUM"
source /home/ivlab3/orbslam_ws/install/local_setup.bash 2>/dev/null
source /opt/ros/jazzy/setup.bash 2>/dev/null

LEFT=/cam0/image_raw; RIGHT=/cam1/image_raw
RELAY_PID=""
if [ -n "$MASKJSON" ]; then
  echo "[orb] relay masking with $MASKJSON"
  python3 /home/ivlab3/fwvio_estimator_ws_wheel/scripts/phase6_pv_mask_relay.py --synthetic-mask \
    > "$LOGDIR/relay_${LABEL}.log" 2>&1 &
  RELAY_PID=$!; sleep 2
  LEFT=/cam0/image_masked; RIGHT=/cam1/image_masked
fi

echo "[orb] launching stereo-inertial label=$LABEL traj=$ORBSLAM_TRAJ_TUM"
ros2 run orbslam3 stereo-inertial "$VOCAB" "$CONFIG" true \
  --ros-args -r imu:=/imu0 -r "camera/left:=$LEFT" -r "camera/right:=$RIGHT" \
  > "$LOGDIR/orbslam_${LABEL}.log" 2>&1 &
SLAM=$!
sleep 5
echo "[orb] playing bag..."
timeout 220 ros2 bag play "$BAG" --rate 1.0 > "$LOGDIR/bag_${LABEL}.log" 2>&1
echo "[orb] bag done; SIGINT to flush traj via destructor, then SIGKILL the hung BA"
kill -INT $SLAM 2>/dev/null; sleep 6
kill -9 $SLAM 2>/dev/null; pkill -9 -f stereo-inertial 2>/dev/null
[ -n "$RELAY_PID" ] && kill -9 $RELAY_PID 2>/dev/null
pkill -9 -f phase6_pv_mask_relay 2>/dev/null
sleep 1
echo "[orb] traj lines: $(wc -l < "$ORBSLAM_TRAJ_TUM" 2>/dev/null || echo 0)"
grep -cE "Reseting|Track lost|LOST" "$LOGDIR/orbslam_${LABEL}.log" 2>/dev/null | sed 's/^/[orb] reset+lost lines: /'
echo "[orb] DONE $LABEL"