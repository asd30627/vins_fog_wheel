#!/usr/bin/env bash
# CARLA town diagnostic scan: 8 towns x 3 routes x 3 durations (30/120/300s).
#   PHASE A: per (town,route) record via fallback LADDER [300s,120s,30s] -> keep longest that COMPLETES
#            (a crashed partial has no imu.csv -> unreplayable; shorter durations finish before the crash point).
#   PHASE B: stop CARLA.  PHASE C: replay the kept recording once (rate 0.5), slice horizons <=achieved;
#            horizons > achieved = CARLA_REC_CRASH. Established recipe (wheel se2 sigma0.001 + soft-failure).
#   Hard-reset CARLA after any record crash (prevents cascade). Town02 known CARLA-load-crash.
PY=/home/ivlab3/miniconda3/envs/carla/bin/python
WS=/home/ivlab3/fwvio_estimator_ws_wheel
CFG=$WS/src/VINS-Fusion-ROS2-jazzy/config/carla
SP=/tmp/claude-1000/-home-ivlab3-fwvio-estimator-ws-wheel/3c414491-a552-45ec-a815-9b8df35ab1e0/scratchpad
OUTDIR=/home/ivlab3/fwvio_estimator_ws_wheel/autonomous_results
ROW=$OUTDIR/town_scan_rows.tsv
IMG=carlasim/carla:0.9.16-maps
CONFIG640=$CFG/carla_stereo_imu_640_R3_b05_wheel.yaml
cd /home/ivlab3/fwvio_ws
export WHEEL_FACTOR_ENABLE=1 WHEEL_MODE=se2 CARLA_SOFT_FAILURE=1 CARLA_WHEEL_SIGMA=0.001

ROUTES=( "rA gentle_turn 0" "rB autopilot 0" "rC gentle_turn 50" )
TOWNS=( Town01 Town02 Town05 Town06 Town07 Town10HD Town11 Town12 )   # Town08/09 not in CARLA
LADDER=( 6000 2400 600 )   # frames: 300s,120s,30s

carla_alive(){ timeout 15 $PY -c "import carla; carla.Client('localhost',3000).get_world().get_map()" 2>/dev/null; }
carla_up(){ carla_alive && return 0
  docker rm -f carla0916 >/dev/null 2>&1; sleep 3
  docker run -d --rm --name carla0916 --gpus all --net=host -e NVIDIA_VISIBLE_DEVICES=all \
    -e NVIDIA_DRIVER_CAPABILITIES=all,graphics,utility,compute -w /workspace --entrypoint bash "$IMG" \
    CarlaUE4.sh -RenderOffScreen -quality-level=Low -nosound -carla-rpc-port=3000 >/dev/null 2>&1
  for i in $(seq 1 24); do sleep 10; carla_alive && return 0; done; return 1; }
hard_reset(){ docker rm -f carla0916 >/dev/null 2>&1; sleep 4; carla_up; }

record_one(){ # town rtag drive spawn frames -> echo achieved_frames(0 if fail). leaves $D with the recording.
  local town="$1" rtag="$2" drive="$3" spawn="$4" frames="$5"
  local D=/mnt/sata4t/datasets/carla_fwvio/${town}__clean__run${rtag}
  local dm="--drive-mode $drive"; [ "$drive" = gentle_turn ] && dm="--drive-mode gentle_turn --base-speed 6.0"
  rm -rf "$D"
  carla_alive || carla_up
  timeout 900 $PY scripts/collect_carla_v2.py --town "$town" --condition clean --run "$rtag" \
    --imu-at-vehicle-center --baseline 0.5 $dm --spawn-index "$spawn" --skip-aux \
    --image-width 640 --image-height 480 --sim-dt 0.01 --settle-sec 2 --static-sec 3 --ramp-sec 5 \
    --ramp-throttle-max 0.30 --frames "$frames" > "$SP/rec_${town}_${rtag}_${frames}.log" 2>&1
  if grep -q "\[collect\] DONE" "$SP/rec_${town}_${rtag}_${frames}.log" && [ -f "$D/imu.csv" ]; then
    echo "$(ls "$D/stereo_left" 2>/dev/null | wc -l)"
  else
    echo 0
  fi
}

[ -f "$ROW" ] || printf "town\troute\tdrive\tspawn\tdur_s\tinit_ok\tcompletion\tATE_m\tearly\tlate\tfail_at_s\tmechanism\tturnfrac\tyawspan\trec_s\n" > "$ROW"

############ PHASE A: RECORD (CARLA up) with fallback ladder ############
echo "===== PHASE A RECORD $(date +%H:%M:%S) ====="
carla_up || { echo "CARLA cannot start; abort"; exit 1; }
for town in "${TOWNS[@]}"; do
  for r in "${ROUTES[@]}"; do
    set -- $r; rtag=$1 drive=$2 spawn=$3
    D=/mnt/sata4t/datasets/carla_fwvio/${town}__clean__run${rtag}
    # skip if a completed recording already exists (has imu.csv + >=300 frames)
    if [ -f "$D/imu.csv" ] && [ "$(ls "$D/stereo_left" 2>/dev/null|wc -l)" -ge 300 ]; then
      echo "REC skip (exists) $town/$rtag frames=$(ls "$D/stereo_left"|wc -l)"; continue
    fi
    ach=0
    for fr in "${LADDER[@]}"; do
      echo "REC $town/$rtag drive=$drive spawn=$spawn frames=$fr $(date +%H:%M:%S)"
      ach=$(record_one "$town" "$rtag" "$drive" "$spawn" "$fr")
      if [ "${ach:-0}" -ge 300 ] 2>/dev/null; then
        echo "  -> COMPLETED frames=$ach (~$((ach/20))s)"; break
      else
        echo "  -> CRASH/FAIL at frames=$fr ; HARD reset CARLA, try shorter"; hard_reset || echo "  WARN carla restart failed"
      fi
    done
    [ "${ach:-0}" -lt 300 ] 2>/dev/null && echo "  $town/$rtag ALL ladder failed (no usable recording)"
  done
done

############ PHASE B: STOP CARLA ############
echo "===== PHASE B STOP CARLA $(date +%H:%M:%S) ====="
docker stop carla0916 >/dev/null 2>&1; sleep 4
echo "  carla running: $(docker ps -q --filter name=carla0916|wc -l) (0=stopped)"

############ PHASE C: REPLAY kept recording + slice horizons ############
echo "===== PHASE C REPLAY $(date +%H:%M:%S) ====="
for town in "${TOWNS[@]}"; do
  for r in "${ROUTES[@]}"; do
    set -- $r; rtag=$1 drive=$2 spawn=$3
    D=/mnt/sata4t/datasets/carla_fwvio/${town}__clean__run${rtag}
    nfr=$(ls "$D/stereo_left" 2>/dev/null | wc -l)
    if [ ! -f "$D/imu.csv" ] || [ "${nfr:-0}" -lt 300 ]; then
      for dur in 30 120 300; do
        printf "%s\t%s\t%s\t%s\t%s\t-\t-\t-\t-\t-\t0\tCARLA_REC_CRASH\t-\t-\t0\n" "$town" "$rtag" "$drive" "$spawn" "$dur" >> "$ROW"
      done
      echo "  $town/$rtag NO usable recording -> 3x CARLA_REC_CRASH"; continue
    fi
    $PY scripts/gen_carla_wheel.py "$D" >/dev/null 2>&1
    $PY scripts/gen_carla_grade_imu.py --seq "$D" --grade ideal_imu >/dev/null 2>&1
    $PY scripts/make_player_imu_yref.py --in "$D/imu_grade_ideal_imu.csv" --out "$D/imu_grade_ideal_imu_yref.csv" --skip-imu-head 0 >/dev/null 2>&1
    export RC_CONFIG="$CONFIG640" REL_WHEEL_PRELOAD="$D/carla_wheel.csv"
    tag="ts_${town}_${rtag}"; RES=/mnt/sata4t/ivlab3_data/fwvio/results/carla_vins/$tag
    echo "  REPLAY $tag frames=$nfr (~$((nfr/20))s) $(date +%H:%M:%S)"
    bash scripts/run_carla_grade_vins.sh "$D" ideal_imu "$tag" 0.5 0 0 > "$SP/vins_${tag}.log" 2>&1
    for dur in 30 120 300; do
      a=$($PY scripts/town_analyze.py "$D" "$RES" "$dur" 2>/dev/null)
      io=$(echo "$a"|grep -oE 'init_ok=[0-9]+'|cut -d= -f2); cp=$(echo "$a"|grep -oE 'completion=[0-9.]+'|cut -d= -f2)
      at=$(echo "$a"|grep -oE 'ATE=[0-9.-]+'|cut -d= -f2); ea=$(echo "$a"|grep -oE 'early=[0-9.]+'|cut -d= -f2)
      la=$(echo "$a"|grep -oE 'late=[0-9.na]+'|cut -d= -f2); fa=$(echo "$a"|grep -oE 'fail_at_s=[0-9.-]+'|cut -d= -f2)
      me=$(echo "$a"|grep -oE 'mechanism=[A-Za-z0-9>._-]+'|cut -d= -f2); tf=$(echo "$a"|grep -oE 'turnfrac=[0-9.-]+'|cut -d= -f2)
      ys=$(echo "$a"|grep -oE 'yawspan=[0-9-]+'|cut -d= -f2); rs=$(echo "$a"|grep -oE 'rec_s=[0-9]+'|cut -d= -f2)
      printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
        "$town" "$rtag" "$drive" "$spawn" "$dur" "${io:-0}" "${cp:-0}" "${at:--}" "${ea:--}" "${la:--}" "${fa:--}" "${me:-ERR}" "${tf:--}" "${ys:--}" "${rs:--}" >> "$ROW"
      echo "    h=${dur}s -> init=$io compl=$cp% ATE=$at mech=$me rec_s=$rs fail_at=$fa"
    done
  done
done
echo "===== TOWN SCAN DONE $(date +%H:%M:%S) ====="
