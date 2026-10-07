#!/usr/bin/env bash
# Run ORB-SLAM3 stereo-inertial on a CARLA fwvio recording with the wrapper pose logger (repair B3).
# doRectify=false (CARLA images are ideal pinhole). Player publishes /carla/{left,right}/image_raw +
# /carla/imu; we remap ORB-SLAM3's imu/camera topics onto them. Force-kill after the player.
#   usage: run_orbslam_carla_logged.sh <run_dir> <label> [stereo_mask_json]
# stereo_mask_json (optional) = {frame:{L:[...],R:[...]}} -> blurs BOTH images (fair stereo mask).
set -o pipefail
REC="${1:?recording dir}"; LABEL="${2:?label}"; SMASKJSON="${3:-}"
LOGDIR=/home/ivlab3/fwvio_estimator_ws_wheel/logs/phase6
VOCAB=/home/ivlab3/orbslam_ws/src/orb-slam3-ros2/vocabulary/ORBvoc.txt
# Auto-pick config by the recording's stereo baseline (build-suitable-for-it): 0.2 -> b02, else 0.5.
BASE_M=$(python3 -c "import json;print(json.load(open('$REC/recording_meta.json')).get('baseline_m',0.5))" 2>/dev/null || echo 0.5)
if [ "$BASE_M" = "0.2" ]; then
  CONFIG=/home/ivlab3/orbslam_ws/src/orb-slam3-ros2/config/stereo-inertial/CARLA_640_b02_stereo_imu.yaml
else
  CONFIG=/home/ivlab3/orbslam_ws/src/orb-slam3-ros2/config/stereo-inertial/CARLA_640_stereo_imu.yaml
fi
echo "[orb-carla] baseline_m=$BASE_M -> config=$(basename $CONFIG)"
PYC=/home/ivlab3/miniconda3/envs/carla/bin/python
WS=/home/ivlab3/fwvio_estimator_ws_wheel
mkdir -p "$LOGDIR"
export DISPLAY=:1 ROS_DOMAIN_ID=81
export ORBSLAM_TRAJ_TUM="$LOGDIR/orbslam_carla_${LABEL}.tum"
rm -f "$ORBSLAM_TRAJ_TUM"
source /home/ivlab3/orbslam_ws/install/local_setup.bash 2>/dev/null
source /opt/ros/jazzy/setup.bash 2>/dev/null

echo "[orb-carla] launch stereo-inertial (doRectify=false) label=$LABEL"
ros2 run orbslam3 stereo-inertial "$VOCAB" "$CONFIG" false \
  --ros-args -r imu:=/carla/imu \
             -r camera/left:=/carla/left/image_raw \
             -r camera/right:=/carla/right/image_raw \
  > "$LOGDIR/orbslam_carla_${LABEL}.log" 2>&1 &
SLAM=$!
sleep 6
IMUCSV="imu_grade_ideal_imu_yref.csv"; [ -f "$REC/$IMUCSV" ] || IMUCSV="imu.csv"
echo "[orb-carla] imu-csv=$IMUCSV"
PLAYER_ARGS="--rec $REC --rate 0.5 --encoding mono8 --imu --imu-csv $IMUCSV"
[ -n "$SMASKJSON" ] && PLAYER_ARGS="$PLAYER_ARGS --stereo-mask-json $SMASKJSON"
echo "[orb-carla] player: $PLAYER_ARGS"
timeout 600 $PYC "$WS/scripts/paper2_carla_stereo_player_masked.py" $PLAYER_ARGS \
  > "$LOGDIR/player_carla_${LABEL}.log" 2>&1
echo "[orb-carla] player done; SIGINT (flush traj) then SIGKILL (hung BA)"
kill -INT $SLAM 2>/dev/null; sleep 6
kill -9 $SLAM 2>/dev/null; pkill -9 -f stereo-inertial 2>/dev/null
sleep 1
echo "[orb-carla] traj lines: $(wc -l < "$ORBSLAM_TRAJ_TUM" 2>/dev/null || echo 0)"
grep -cE "Reseting|not enough|Not enough|Fail|fail|LOST|lost" "$LOGDIR/orbslam_carla_${LABEL}.log" 2>/dev/null | sed 's/^/[orb-carla] warn-lines: /'
grep -m1 -E "VIBA|Map created|creating new map" "$LOGDIR/orbslam_carla_${LABEL}.log" 2>/dev/null
echo "[orb-carla] DONE $LABEL"