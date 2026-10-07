#!/usr/bin/env bash
# Paper-2 Part 2 — run ONE baseline VINS (stereo+IMU, 640, no wheel, ideal IMU) on a CARLA recording,
# offline (CARLA service NOT needed), then gate ATE. Reusable for the baseline set + masked variants.
#   usage: paper2_vins_run_one.sh <recording_dir> <out_tag> [rate] [stereo_left_subdir]
# stereo_left_subdir (optional): name of an alternate left-image dir under <rec> (for masked variants);
#   default uses the recording's own stereo_left via the stock player.
set -o pipefail
REC="${1:?recording dir}"; TAG="${2:?out tag}"; RATE="${3:-0.5}"
WS=/home/ivlab3/fwvio_estimator_ws_wheel
FW=/home/ivlab3/fwvio_ws
# b05_gm = correct extrinsic (baseline 0.5, t=±0.25) — byte-identical to the working historical Town01
# config. (b02 gave 0 vio rows: wrong baseline breaks stereo init.) Use rate 0.5 (working recipe);
# rate 0.2 diverged. Override with RC_CONFIG env.
CFG="${RC_CONFIG:-$WS/src/VINS-Fusion-ROS2-jazzy/config/carla/carla_stereo_imu_640_R3_b05_gm.yaml}"
PYC=/home/ivlab3/miniconda3/envs/carla/bin/python
OUTROOT=/mnt/sata4t/ivlab3_data/fwvio/results/paper2_vinsaware
OUTDIR="$OUTROOT/$TAG"; mkdir -p "$OUTDIR"

# 1) IMU grade + proper yref (skip-imu-head 150 = drop power-on spike; the WORKING historical recipe).
#    REL_IMU_GRADE (env, default ideal_imu): gyro grade (ideal_imu|military_fog|industrial_fog|precision_mems).
#    Regenerate only if the yref is missing (grades are deterministic; cached).
GRADE="${REL_IMU_GRADE:-ideal_imu}"
if [ ! -f "$REC/imu_grade_${GRADE}_yref.csv" ]; then
  $PYC "$FW/scripts/gen_carla_grade_imu.py" --seq "$REC" --grade "$GRADE" --seed 42 > "$OUTDIR/imu_gen.log" 2>&1
  $PYC "$FW/scripts/make_player_imu_yref.py" --in "$REC/imu_grade_${GRADE}.csv" \
       --out "$REC/imu_grade_${GRADE}_yref.csv" --skip-imu-head 150 >> "$OUTDIR/imu_gen.log" 2>&1
fi

# 2) VINS node + stereo player (pure-file replay). Config output_path rewritten to OUTDIR.
TMPCFG="$OUTDIR/config.yaml"
sed "s#^output_path:.*#output_path: \"$OUTDIR/\"#" "$CFG" > "$TMPCFG"
cp -f "$(dirname "$CFG")"/cam0_pinhole_640.yaml "$(dirname "$CFG")"/cam1_pinhole_640.yaml "$OUTDIR/"
VINS_BIN="$WS/install/vins/lib/vins/vins_node"
source /opt/ros/jazzy/setup.bash 2>/dev/null; source "$WS/install/setup.bash" 2>/dev/null
echo "[p2-vins] bin=$(sha256sum $VINS_BIN|cut -c1-12) rec=$(basename $REC) tag=$TAG rate=$RATE cfg=$(basename $CFG)" | tee "$OUTDIR/run_header.txt"
"$VINS_BIN" "$TMPCFG" --ros-args > "$OUTDIR/vins.log" 2>&1 &
VPID=$!
sleep 8
PLAYER_ARGS="--rec $REC --rate $RATE --encoding mono8 --imu --imu-csv imu_grade_${GRADE}_yref.csv"
# MASK_JSON env (optional): per-frame dynamic-object bboxes to suppress in LEFT image (Phase C).
# Uses the Paper-2 masked player (byte-identical to stock when --mask-json absent).
[ -n "$MASK_JSON" ] && PLAYER_ARGS="$PLAYER_ARGS --mask-json $MASK_JSON"
$PYC "$WS/scripts/paper2_carla_stereo_player_masked.py" $PLAYER_ARGS > "$OUTDIR/player.log" 2>&1
sleep 5
kill "$VPID" 2>/dev/null; sleep 2; kill -9 "$VPID" 2>/dev/null
rows=$(wc -l < "$OUTDIR/vio.csv" 2>/dev/null || echo 0)
echo "[p2-vins] DONE tag=$TAG vio_rows=$rows -> $OUTDIR" | tee -a "$OUTDIR/run_header.txt"

# 3) gate (ATE/scale/fail)
python3 "$FW/scripts/carla_gate.py" "$REC" "$OUTDIR" "$TAG" 2>&1 | tee "$OUTDIR/gate.txt"
