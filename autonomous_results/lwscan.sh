#!/usr/bin/env bash
# Phase-separated lightweight scan pipeline.
#   PHASE A: record all specs (--skip-aux) with CARLA up (+crash restart)
#   PHASE B: stop CARLA (replay needs no CARLA; removes 300% CPU contention)
#   PHASE C: replay each (CARLA stopped) + walltime lag guard + gate + classify
# Specs file: $SPECS_FILE, lines: town cond motion res run
PY=/home/ivlab3/miniconda3/envs/carla/bin/python
WS=/home/ivlab3/fwvio_estimator_ws_wheel
CFG=$WS/src/VINS-Fusion-ROS2-jazzy/config/carla
SP=/tmp/claude-1000/-home-ivlab3-fwvio-estimator-ws-wheel/4b1d1a98-a243-46a9-9784-79394714f7cc/scratchpad
SPECS_FILE="${SPECS_FILE:-$SP/lwscan_specs.txt}"
SUM="${SUM_FILE:-$SP/lwscan_summary.txt}"; ROW="${ROW_FILE:-$SP/lwscan_rows.tsv}"
LAG_THRESH="${LAG_THRESH:-260}"   # player publish walltime (s) above which we suspect replay lag -> rerun once
cd /home/ivlab3/fwvio_ws
export WHEEL_FACTOR_ENABLE=1 WHEEL_MODE=se2 CARLA_SOFT_FAILURE=1 CARLA_WHEEL_SIGMA=0.001

carla_alive(){ timeout 12 $PY -c "import carla; carla.Client('localhost',3000).get_world().get_map()" 2>/dev/null; }
carla_up(){ carla_alive && return 0
  docker rm -f carla0916 >/dev/null 2>&1
  docker run -d --rm --name carla0916 --gpus all --net=host -e NVIDIA_VISIBLE_DEVICES=all \
    -e NVIDIA_DRIVER_CAPABILITIES=all,graphics,utility,compute -w /workspace carlasim/carla:0.9.16 \
    bash CarlaUE4.sh -RenderOffScreen -quality-level=Low -nosound -carla-rpc-port=3000 >/dev/null 2>&1
  for i in $(seq 1 18); do sleep 10; carla_alive && return 0; done; return 1; }
config_for(){ [ "$1" = 640 ] && echo "$CFG/carla_stereo_imu_640_R3_b05_wheel.yaml" || echo "$CFG/carla_stereo_imu_1280_R3_b05_wheel.yaml"; }
wh_for(){ [ "$1" = 640 ] && echo "480" || echo "720"; }
publish_walltime(){ # from player.log: done - start (ROS log ts in [..])
  local pl="$1"; local a b
  a=$(grep 'frames (dropped' "$pl" 2>/dev/null | grep -oE '\[[0-9]{10}' | tr -d '[' | head -1)
  b=$(grep 'done publishing' "$pl" 2>/dev/null | grep -oE '\[[0-9]{10}' | tr -d '[' | head -1)
  [ -n "$a" ] && [ -n "$b" ] && echo $((b-a)) || echo "-1"; }
# scale-based class: SCALE_PASS = early&late in [0.9,1.1] + completed (soft-fail count is separate)
classify(){ awk -v e="$1" -v l="$2" 'BEGIN{
  if(e==""||l==""||l=="n/a"||e=="nan"){print "INIT_FAIL"; exit}
  if(e>=0.9&&e<=1.1&&l>=0.9&&l<=1.1) print "SCALE_PASS"; else print "INIT_FAIL"}'; }

: > "$SUM"; printf "town\tcond\tmotion\tres\trun\tseed\tearly\tlate\tfull\tATE\tfail\twalltime\tCLASS\n" > "$ROW"

############ PHASE A: RECORD (CARLA up) ############
echo "===== PHASE A: RECORD $(date +%H:%M:%S) =====" | tee -a "$SUM"
carla_up || { echo "CARLA cannot start; abort" | tee -a "$SUM"; exit 1; }
while read -r town cond motion res run; do
  [ -z "$town" ] && continue
  D=/mnt/sata4t/datasets/carla_fwvio/${town}__${cond}__run${run}
  dm="--drive-mode $motion"; [ "$motion" = gentle_turn ] && dm="--drive-mode gentle_turn --base-speed 6.0"
  echo "REC $town/$res/$run $(date +%H:%M:%S)" | tee -a "$SUM"
  carla_alive || carla_up
  $PY scripts/collect_carla_v2.py --town "$town" --condition "$cond" --run "$run" \
    --imu-at-vehicle-center --baseline 0.5 $dm --skip-aux --image-width "$res" --image-height "$(wh_for $res)" \
    --sim-dt 0.01 --settle-sec 2 --static-sec 3 --ramp-sec 5 --ramp-throttle-max 0.30 --frames 600 \
    > "$SP/rec_${town}_${res}_${run}.log" 2>&1
  grep -q "\[collect\] DONE" "$SP/rec_${town}_${res}_${run}.log" || { echo "  REC FAIL $town/$res/$run"|tee -a "$SUM"; carla_alive||carla_up; }
done < "$SPECS_FILE"

############ PHASE B: STOP CARLA ############
echo "===== PHASE B: STOP CARLA $(date +%H:%M:%S) =====" | tee -a "$SUM"
docker stop carla0916 >/dev/null 2>&1; sleep 4
echo "  carla running: $(docker ps -q --filter name=carla0916|wc -l) (0=stopped)" | tee -a "$SUM"

############ PHASE C: REPLAY (CARLA stopped) ############
echo "===== PHASE C: REPLAY $(date +%H:%M:%S) =====" | tee -a "$SUM"
do_replay(){ # town cond motion res run tag
  local town="$1" cond="$2" motion="$3" res="$4" run="$5" tag="$6"
  local D=/mnt/sata4t/datasets/carla_fwvio/${town}__${cond}__run${run}
  export RC_CONFIG="$(config_for $res)" REL_WHEEL_PRELOAD="$D/carla_wheel.csv"
  $PY scripts/gen_carla_wheel.py "$D" >/dev/null 2>&1
  $PY scripts/gen_carla_grade_imu.py --seq "$D" --grade ideal_imu >/dev/null 2>&1
  $PY scripts/make_player_imu_yref.py --in "$D/imu_grade_ideal_imu.csv" --out "$D/imu_grade_ideal_imu_yref.csv" --skip-imu-head 0 >/dev/null 2>&1
  bash scripts/run_carla_grade_vins.sh "$D" ideal_imu "$tag" 0.2 0 0 > "$SP/vins_${tag}.log" 2>&1
  python3 scripts/carla_gate.py "$D" "/mnt/sata4t/ivlab3_data/fwvio/results/carla_vins/$tag" "$tag" 2>&1
}
while read -r town cond motion res run; do
  [ -z "$town" ] && continue
  D=/mnt/sata4t/datasets/carla_fwvio/${town}__${cond}__run${run}
  tag="lw_${town}_${res}_${run}"
  [ -d "$D" ] && grep -q "\[collect\] DONE" "$SP/rec_${town}_${res}_${run}.log" 2>/dev/null || { printf "%s\t%s\t%s\t%s\t%s\t-\t-\t-\t-\t-\t-\t-\tRUN_ERROR\n" "$town" "$cond" "$motion" "$res" "$run" >> "$ROW"; echo "  $tag RUN_ERROR(no rec)"|tee -a "$SUM"; continue; }
  seed=$($PY -c "import json;print(json.load(open('$D/recording_meta.json'))['seed'])" 2>/dev/null)
  g=$(do_replay "$town" "$cond" "$motion" "$res" "$run" "$tag")
  wt=$(publish_walltime "/mnt/sata4t/ivlab3_data/fwvio/results/carla_vins/$tag/player.log")
  # lag guard: rerun once if walltime suspiciously high
  if [ "$wt" -gt "$LAG_THRESH" ] 2>/dev/null; then
    echo "  $tag walltime=${wt}s > $LAG_THRESH -> rerun (lag guard)" | tee -a "$SUM"
    g=$(do_replay "$town" "$cond" "$motion" "$res" "$run" "$tag")
    wt=$(publish_walltime "/mnt/sata4t/ivlab3_data/fwvio/results/carla_vins/$tag/player.log")
  fi
  early=$(echo "$g"|grep -oE 'early=[0-9.]+'|cut -d= -f2); late=$(echo "$g"|grep -oE 'late=[0-9.na/]+'|head -1|cut -d= -f2)
  full=$(echo "$g"|grep -oE 'full=[0-9.e+]+'|cut -d= -f2); ate=$(echo "$g"|grep -oE 'ATE_se3=[0-9.e+]+'|cut -d= -f2)
  fail=$(echo "$g"|grep -oE 'fail=[0-9]+'|head -1|cut -d= -f2)
  cls=$(classify "$early" "$late")
  [ "$wt" -gt "$LAG_THRESH" ] 2>/dev/null && cls="${cls}_LAG?"
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$town" "$cond" "$motion" "$res" "$run" "$seed" "$early" "$late" "$full" "$ate" "$fail" "$wt" "$cls" >> "$ROW"
  echo "  $tag -> $cls early=$early late=$late softfail=$fail wt=${wt}s" | tee -a "$SUM"
done < "$SPECS_FILE"
echo "===== LWSCAN DONE $(date +%H:%M:%S) =====" | tee -a "$SUM"
