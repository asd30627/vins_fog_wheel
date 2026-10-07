#!/usr/bin/env bash
# Per-grade degradation sweep (BASELINE, no AI). Replay-only on existing 1280 recordings, CARLA stopped.
# For each recording x each IMU grade: SCALE_PASS? + scale-error. Fixed recipe (1280 wheel).
PY=/home/ivlab3/miniconda3/envs/carla/bin/python
WS=/home/ivlab3/fwvio_estimator_ws_wheel
CFG=$WS/src/VINS-Fusion-ROS2-jazzy/config/carla
SP=/tmp/claude-1000/-home-ivlab3-fwvio-estimator-ws-wheel/4b1d1a98-a243-46a9-9784-79394714f7cc/scratchpad
SUM=$SP/grade_sweep_summary.txt; ROW=$SP/grade_sweep_rows.tsv
cd /home/ivlab3/fwvio_ws
export RC_CONFIG="$CFG/carla_stereo_imu_1280_R3_b05_wheel.yaml"
export WHEEL_FACTOR_ENABLE=1 WHEEL_MODE=se2 CARLA_SOFT_FAILURE=1 CARLA_WHEEL_SIGMA=0.001
classify(){ awk -v e="$1" -v l="$2" 'BEGIN{ if(e==""||l==""||l=="n/a"||e=="nan"){print "INIT_FAIL";exit}
  if(e>=0.9&&e<=1.1&&l>=0.9&&l<=1.1)print "SCALE_PASS"; else print "INIT_FAIL"}'; }
walltime(){ local pl="$1" a b; a=$(grep 'frames (dropped' "$pl" 2>/dev/null|grep -oE '\[[0-9]{10}'|tr -d '['|head -1)
  b=$(grep 'done publishing' "$pl" 2>/dev/null|grep -oE '\[[0-9]{10}'|tr -d '['|head -1); [ -n "$a" ]&&[ -n "$b" ]&&echo $((b-a))||echo -1; }

docker stop carla0916 >/dev/null 2>&1; sleep 3   # replay needs no CARLA; remove contention
: > "$SUM"; printf "recording\ttown\tgrade\tearly\tlate\tfull\tATE\tsoftfail\twalltime\tCLASS\n" > "$ROW"

RECS="Town10HD__clean__rungturn1 Town10HD__clean__rungtgen1 Town10HD__clean__rungtgen4 Town01__clean__runscangtA Town01__clean__runscangtB Town04__clean__runscangtA Town05__clean__runscangtA Town05__clean__runscangtB"
GRADES="ideal_imu military_fog industrial_fog precision_mems"

for rec in $RECS; do
  D=/mnt/sata4t/datasets/carla_fwvio/$rec
  [ -d "$D" ] || { echo "MISSING $rec" | tee -a "$SUM"; continue; }
  town=$(echo "$rec" | cut -d_ -f1)
  $PY scripts/gen_carla_wheel.py "$D" >/dev/null 2>&1
  export REL_WHEEL_PRELOAD="$D/carla_wheel.csv"
  for grade in $GRADES; do
    tag="gsweep_${rec}_${grade}"
    echo "#### $rec / $grade $(date +%H:%M:%S) ####" | tee -a "$SUM"
    $PY scripts/gen_carla_grade_imu.py --seq "$D" --grade "$grade" >/dev/null 2>&1
    $PY scripts/make_player_imu_yref.py --in "$D/imu_grade_${grade}.csv" --out "$D/imu_grade_${grade}_yref.csv" --skip-imu-head 0 >/dev/null 2>&1
    # run vins with this grade's IMU (override RC_IMUCSV via the run script's env)
    RC_IMUCSV="imu_grade_${grade}_yref.csv" bash scripts/run_carla_grade_vins.sh "$D" "$grade" "$tag" 0.2 0 0 > "$SP/vins_${tag}.log" 2>&1
    RES=/mnt/sata4t/ivlab3_data/fwvio/results/carla_vins/$tag
    g=$(python3 scripts/carla_gate.py "$D" "$RES" "$tag" 2>&1)
    early=$(echo "$g"|grep -oE 'early=[0-9.]+'|cut -d= -f2); late=$(echo "$g"|grep -oE 'late=[0-9.na/]+'|head -1|cut -d= -f2)
    full=$(echo "$g"|grep -oE 'full=[0-9.e+]+'|cut -d= -f2); ate=$(echo "$g"|grep -oE 'ATE_se3=[0-9.e+]+'|cut -d= -f2)
    sf=$(echo "$g"|grep -oE 'fail=[0-9]+'|head -1|cut -d= -f2); wt=$(walltime "$RES/player.log")
    cls=$(classify "$early" "$late")
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$rec" "$town" "$grade" "$early" "$late" "$full" "$ate" "$sf" "$wt" "$cls" >> "$ROW"
    echo "  -> $cls early=$early late=$late softfail=$sf wt=${wt}s" | tee -a "$SUM"
  done
done
echo "GRADE SWEEP DONE $(date +%H:%M:%S)" | tee -a "$SUM"
