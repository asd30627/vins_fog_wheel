#!/usr/bin/env bash
# 30s init-success scan. Fixed recipe (NO change to Huber/wheel_sigma/config/rate/drop_head).
PY=/home/ivlab3/miniconda3/envs/carla/bin/python
WS=/home/ivlab3/fwvio_estimator_ws_wheel
SP=/tmp/claude-1000/-home-ivlab3-fwvio-estimator-ws-wheel/4b1d1a98-a243-46a9-9784-79394714f7cc/scratchpad
SUM=$SP/scan30s_summary.txt
ROW=$SP/scan30s_rows.tsv
cd /home/ivlab3/fwvio_ws
export RC_CONFIG="$WS/src/VINS-Fusion-ROS2-jazzy/config/carla/carla_stereo_imu_1280_R3_b05_wheel.yaml"
export WHEEL_FACTOR_ENABLE=1 WHEEL_MODE=se2 CARLA_SOFT_FAILURE=1 CARLA_WHEEL_SIGMA=0.001

# pipeline: town cond motion run do_record
pipeline () {
  local town="$1" cond="$2" motion="$3" run="$4" do_record="$5"
  local D=/mnt/sata4t/datasets/carla_fwvio/${town}__${cond}__run${run}
  local tag="scan_${town}_${cond}_${motion}_${run}"
  echo "############ $tag  $(date +%H:%M:%S) ############" | tee -a "$SUM"
  if [ "$do_record" = "1" ]; then
    local dmflags="--drive-mode $motion"
    [ "$motion" = "gentle_turn" ] && dmflags="--drive-mode gentle_turn --base-speed 6.0"
    $PY scripts/collect_carla_v2.py --town "$town" --condition "$cond" --run "$run" \
      --imu-at-vehicle-center --baseline 0.5 $dmflags \
      --sim-dt 0.01 --settle-sec 2 --static-sec 3 --ramp-sec 5 --ramp-throttle-max 0.30 --frames 600 \
      > "$SP/rec_${tag}.log" 2>&1
    if ! grep -q "\[collect\] DONE" "$SP/rec_${tag}.log"; then
      echo "  RECORD FAILED -> RUN_ERROR" | tee -a "$SUM"; tail -4 "$SP/rec_${tag}.log" | tee -a "$SUM"
      printf "%s\t%s\t%s\t-\t%s\t30s\t-\t-\t-\t-\t-\tRUN_ERROR\trecord_failed\n" "$tag" "$town" "$cond" "$motion" >> "$ROW"
      return
    fi
  fi
  if [ ! -d "$D" ]; then
    echo "  NO DATA DIR -> RUN_ERROR" | tee -a "$SUM"
    printf "%s\t%s\t%s\t-\t%s\t30s\t-\t-\t-\t-\t-\tRUN_ERROR\tno_data\n" "$tag" "$town" "$cond" "$motion" >> "$ROW"; return
  fi
  local seed dm
  seed=$($PY -c "import json;print(json.load(open('$D/recording_meta.json'))['seed'])" 2>/dev/null)
  dm=$($PY -c "import json;print(json.load(open('$D/recording_meta.json')).get('drive_mode'))" 2>/dev/null)
  # preprocessing
  $PY scripts/gen_carla_wheel.py "$D" > "$SP/pre_${tag}.log" 2>&1
  $PY scripts/gen_carla_grade_imu.py --seq "$D" --grade ideal_imu >> "$SP/pre_${tag}.log" 2>&1
  $PY scripts/make_player_imu_yref.py --in "$D/imu_grade_ideal_imu.csv" --out "$D/imu_grade_ideal_imu_yref.csv" --skip-imu-head 0 >> "$SP/pre_${tag}.log" 2>&1
  export REL_WHEEL_PRELOAD="$D/carla_wheel.csv"
  bash scripts/run_carla_grade_vins.sh "$D" ideal_imu "$tag" 0.2 0 0 > "$SP/vins_${tag}.log" 2>&1
  local RES=/mnt/sata4t/ivlab3_data/fwvio/results/carla_vins/$tag
  local rerr=""
  grep -qiE "double free|corruption" "$RES/vins.log" 2>/dev/null && rerr="double_free"
  [ -f "$RES/vio.csv" ] || rerr="no_vio"
  local gate; gate=$(python3 scripts/carla_gate.py "$D" "$RES" "$tag" 2>&1)
  echo "$gate" | tee -a "$SUM"; echo "" >> "$SUM"
  local early late full ate fail rows pass
  early=$(echo "$gate" | grep -oE 'early=[0-9.]+' | cut -d= -f2)
  late=$(echo "$gate"  | grep -oE 'late=[0-9.na/]+' | head -1 | cut -d= -f2)
  full=$(echo "$gate"  | grep -oE 'full=[0-9.]+' | cut -d= -f2)
  ate=$(echo "$gate"   | grep -oE 'ATE_se3=[0-9.]+' | cut -d= -f2)
  fail=$(echo "$gate"  | grep -oE 'fail=[0-9]+' | head -1 | cut -d= -f2)
  rows=$(echo "$gate"  | grep -oE 'rows=[0-9]+' | head -1 | cut -d= -f2)
  if echo "$gate" | grep -q ': PASS \*\*\*'; then pass=PASS; else pass=NOTPASS; fi
  local cls note2
  if [ -n "$rerr" ]; then cls="RUN_ERROR"; note2="$rerr"
  elif [ "$pass" = "PASS" ]; then cls="PASS"; note2="rows=$rows"
  else cls="INIT_FAIL"; note2="rows=$rows"; fi
  printf "%s\t%s\t%s\t%s\t%s\t30s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
     "$tag" "$town" "$cond" "$seed" "$dm" "$early" "$late" "$full" "$ate" "$fail" "$cls" "$note2" >> "$ROW"
  echo "  -> $cls (early=$early late=$late full=$full ATE=$ate fail=$fail)" | tee -a "$SUM"
}

: > "$SUM"
printf "tag\ttown\tcond\tseed\tdrive_mode\tdur\tearly\tlate\tfull\tATE\tfail\tCLASS\tnotes\n" > "$ROW"

# B0: existing gtgen1-4 (no record) — Town10HD clean gentle_turn, 4 seeds
for g in gtgen1 gtgen2 gtgen3 gtgen4; do pipeline Town10HD clean gentle_turn "$g" 0; done
# B1: Town01-05 x clean x gentle_turn x 2 seeds
for t in Town01 Town02 Town03 Town04 Town05; do
  for s in scangtA scangtB; do pipeline "$t" clean gentle_turn "$s" 1; done
done

echo "ALL STAGE1 SCAN DONE  $(date +%H:%M:%S)" | tee -a "$SUM"
