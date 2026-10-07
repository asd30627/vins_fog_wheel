#!/usr/bin/env bash
# IMU accel-noise sweep: on towns that RECORD 300s, does lower noise_accel_stddev let VINS survive longer
# (acc-bias divergence is accel-driven; ideal_imu replay uses recorded accel verbatim).
# Sweep accel-noise {0.002 (10x low), 0.0002 (100x low)}; compare to 0.02 baseline (from main scan).
# TARGETS passed as args lines via TARGETS env or default below. Phase-separated (record CARLA-up, replay CARLA-down).
PY=/home/ivlab3/miniconda3/envs/carla/bin/python
WS=/home/ivlab3/fwvio_estimator_ws_wheel
CFG=$WS/src/VINS-Fusion-ROS2-jazzy/config/carla
SP=/tmp/claude-1000/-home-ivlab3-fwvio-estimator-ws-wheel/3c414491-a552-45ec-a815-9b8df35ab1e0/scratchpad
OUTDIR=/home/ivlab3/fwvio_estimator_ws_wheel/autonomous_results
ROW=$OUTDIR/imu_sweep_rows.tsv
IMG=carlasim/carla:0.9.16-maps
CONFIG640=$CFG/carla_stereo_imu_640_R3_b05_wheel.yaml
cd /home/ivlab3/fwvio_ws
export WHEEL_FACTOR_ENABLE=1 WHEEL_MODE=se2 CARLA_SOFT_FAILURE=1 CARLA_WHEEL_SIGMA=0.001

# targets: "town rtag drive spawn"  (override via TARGETS_FILE)
DEFAULT_TARGETS=( "Town01 rA gentle_turn 0" "Town06 rA gentle_turn 0" )
if [ -n "$TARGETS_FILE" ] && [ -f "$TARGETS_FILE" ]; then mapfile -t TARGETS < "$TARGETS_FILE"; else TARGETS=("${DEFAULT_TARGETS[@]}"); fi
NOISES=( 0.002 0.0002 )

carla_alive(){ timeout 15 $PY -c "import carla; carla.Client('localhost',3000).get_world().get_map()" 2>/dev/null; }
carla_up(){ carla_alive && return 0
  docker rm -f carla0916 >/dev/null 2>&1; sleep 3
  docker run -d --rm --name carla0916 --gpus all --net=host -e NVIDIA_VISIBLE_DEVICES=all \
    -e NVIDIA_DRIVER_CAPABILITIES=all,graphics,utility,compute -w /workspace --entrypoint bash "$IMG" \
    CarlaUE4.sh -RenderOffScreen -quality-level=Low -nosound -carla-rpc-port=3000 >/dev/null 2>&1
  for i in $(seq 1 24); do sleep 10; carla_alive && return 0; done; return 1; }
hard_reset(){ docker rm -f carla0916 >/dev/null 2>&1; sleep 4; carla_up; }
nz_tag(){ echo "$1" | sed 's/\./p/g'; }   # 0.002->0p002, 0.0002->0p0002 (no collision)

[ -f "$ROW" ] || printf "town\troute\taccel_noise\trec_s\tinit_ok\tcompletion300\tATE_m\tearly\tlate\tfail_at_s\tmechanism\n" > "$ROW"

echo "===== IMU SWEEP PHASE A RECORD $(date +%H:%M:%S) ====="
carla_up || { echo "CARLA cannot start; abort"; exit 1; }
for t in "${TARGETS[@]}"; do
  set -- $t; town=$1 rtag=$2 drive=$3 spawn=$4
  for an in "${NOISES[@]}"; do
    run="${rtag}_an$(nz_tag $an)"; D=/mnt/sata4t/datasets/carla_fwvio/${town}__clean__run${run}
    if [ -f "$D/imu.csv" ] && [ "$(ls "$D/stereo_left" 2>/dev/null|wc -l)" -ge 300 ]; then echo "skip(exists) $town/$run"; continue; fi
    dm="--drive-mode $drive"; [ "$drive" = gentle_turn ] && dm="--drive-mode gentle_turn --base-speed 6.0"
    echo "REC $town/$rtag accel_noise=$an $(date +%H:%M:%S)"; rm -rf "$D"; carla_alive||carla_up
    timeout 900 $PY scripts/collect_carla_v2.py --town "$town" --condition clean --run "$run" \
      --imu-at-vehicle-center --baseline 0.5 $dm --spawn-index "$spawn" --accel-noise "$an" --skip-aux \
      --image-width 640 --image-height 480 --sim-dt 0.01 --settle-sec 2 --static-sec 3 --ramp-sec 5 \
      --ramp-throttle-max 0.30 --frames 6000 > "$SP/imusw_rec_${town}_${run}.log" 2>&1
    grep -q "\[collect\] DONE" "$SP/imusw_rec_${town}_${run}.log" && [ -f "$D/imu.csv" ] || { echo "  REC FAIL $town/$run -> hard reset"; hard_reset; }
  done
done
echo "===== IMU SWEEP PHASE B STOP CARLA $(date +%H:%M:%S) ====="
docker stop carla0916 >/dev/null 2>&1; sleep 4

echo "===== IMU SWEEP PHASE C REPLAY $(date +%H:%M:%S) ====="
emit(){ # town rtag accel_noise D
  local town="$1" rtag="$2" an="$3" D="$4"
  local nfr=$(ls "$D/stereo_left" 2>/dev/null|wc -l)
  if [ ! -f "$D/imu.csv" ] || [ "${nfr:-0}" -lt 300 ]; then
    printf "%s\t%s\t%s\t0\t-\t-\t-\t-\t-\t0\tCARLA_REC_CRASH\n" "$town" "$rtag" "$an" >> "$ROW"; echo "  $town/$rtag an=$an REC_CRASH"; return; fi
  $PY scripts/gen_carla_wheel.py "$D" >/dev/null 2>&1
  $PY scripts/gen_carla_grade_imu.py --seq "$D" --grade ideal_imu >/dev/null 2>&1
  $PY scripts/make_player_imu_yref.py --in "$D/imu_grade_ideal_imu.csv" --out "$D/imu_grade_ideal_imu_yref.csv" --skip-imu-head 0 >/dev/null 2>&1
  export RC_CONFIG="$CONFIG640" REL_WHEEL_PRELOAD="$D/carla_wheel.csv"
  local tag="imusw_${town}_${rtag}_an$(nz_tag $an)"; local RES=/mnt/sata4t/ivlab3_data/fwvio/results/carla_vins/$tag
  bash scripts/run_carla_grade_vins.sh "$D" ideal_imu "$tag" 0.5 0 0 > "$SP/imusw_vins_${tag}.log" 2>&1
  local a=$($PY scripts/town_analyze.py "$D" "$RES" 300 2>/dev/null)
  local io=$(echo "$a"|grep -oE 'init_ok=[0-9]+'|cut -d= -f2) cp=$(echo "$a"|grep -oE 'completion=[0-9.]+'|cut -d= -f2)
  local at=$(echo "$a"|grep -oE 'ATE=[0-9.-]+'|cut -d= -f2) ea=$(echo "$a"|grep -oE 'early=[0-9.]+'|cut -d= -f2)
  local la=$(echo "$a"|grep -oE 'late=[0-9.na]+'|cut -d= -f2) fa=$(echo "$a"|grep -oE 'fail_at_s=[0-9.-]+'|cut -d= -f2)
  local me=$(echo "$a"|grep -oE 'mechanism=[A-Za-z0-9>._-]+'|cut -d= -f2) rs=$(echo "$a"|grep -oE 'rec_s=[0-9]+'|cut -d= -f2)
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$town" "$rtag" "$an" "${rs:--}" "${io:-0}" "${cp:-0}" "${at:--}" "${ea:--}" "${la:--}" "${fa:--}" "${me:-ERR}" >> "$ROW"
  echo "  $town/$rtag an=$an -> init=$io compl=$cp% ATE=$at mech=$me fail_at=$fa rec_s=$rs"
}
for t in "${TARGETS[@]}"; do
  set -- $t; town=$1 rtag=$2 drive=$3 spawn=$4
  # baseline 0.02 from main scan recording
  emit "$town" "$rtag" 0.02 "/mnt/sata4t/datasets/carla_fwvio/${town}__clean__run${rtag}"
  for an in "${NOISES[@]}"; do
    emit "$town" "$rtag" "$an" "/mnt/sata4t/datasets/carla_fwvio/${town}__clean__run${rtag}_an$(nz_tag $an)"
  done
done
echo "===== IMU SWEEP DONE $(date +%H:%M:%S) ====="
