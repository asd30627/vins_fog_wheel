#!/usr/bin/env bash
# Disentangle FOG-hardware vs gyr_w-config: run 3 configs on ONE urban seq, SAME pipeline (fixedext).
#   1) imu + xsens      = real xsens gyro + xsens config (GYR_W 1e-4)   [real-xsens reference]
#   2) imu + fog_xsens  = real xsens gyro + FOG config   (GYR_W 1e-5)   [CONTROL]
#   3) fog + fog_xsens  = real FOG gyro   + FOG config   (GYR_W 1e-5)   [real-FOG reference]
# If control(2) ~ xsens(1) -> gain is FOG HARDWARE; if control(2) ~ fog(3) -> gain is the CONFIG.
set -o pipefail
SEQ="${1:-urban28-pankyo}"
R=/home/ivlab3/fwvio_estimator_ws_wheel/scripts/run_one_p1_baseline.sh
SR=/mnt/sata4t/datasets/kaist_complex_urban/extracted/$SEQ
GT=$SR/pose/$SEQ/global_pose.tum
PB=/home/ivlab3/fwvio_estimator_ws_wheel/src/kaist_player/config/$(echo $SEQ|tr '-' '_')   # template base
PCFG="${PB}.yaml"; PCFGFOG="${PB}_fog.yaml"
# fallback: seqs without their own template reuse urban28's _fog template; the runner's
# replace_seq_placeholders substitutes urban28-pankyo -> this seq, so paths resolve correctly.
[ -f "$PCFGFOG" ] || PCFGFOG=/home/ivlab3/fwvio_estimator_ws_wheel/src/kaist_player/config/urban28_pankyo_fog.yaml
[ -f "$PCFG" ] || PCFG="${PCFGFOG}"
WW=/mnt/sata4t/ivlab3_data/fwvio/results/p1_wheel_v2/_work_wheel
OUT=/mnt/sata4t/ivlab3_data/fwvio/results/control_config_vs_fog/$SEQ; mkdir -p "$OUT"
export USE_EXPLICIT_FIXEDEXT=1
run(){ # mode noise template tag
  echo "[$(date +%H:%M:%S)] === $4 : mode=$1 noise=$2 ==="
  bash "$R" "$SEQ" "$SR" "$3" "$GT" "$1" "$2" > "$OUT/run_$4.log" 2>&1
  local src="$WW/$1/$SEQ/vins_raw/vio.tum"
  if [ -s "$src" ]; then cp "$src" "$OUT/${4}.tum"; echo "[$(date +%H:%M:%S)] $4 DONE rows=$(wc -l <$src)"; else echo "[$(date +%H:%M:%S)] $4 FAILED (no vio.tum)"; tail -5 "$OUT/run_$4.log"; fi
}
# Use the _fog template for ALL runs: it has imu_source (in-place replace, no append-break),
# xsens imu_csv, and fog_csv. In imu mode the runner sets imu_source=xsens -> player uses xsens
# gyro only (fog_csv ignored); in fog mode imu_source=fog_xsens -> uses fog.csv. Clean disentangle.
run imu xsens     "$PCFGFOG" xsens
run imu fog_xsens "$PCFGFOG" control
run fog fog_xsens "$PCFGFOG" fog
echo "[$(date +%H:%M:%S)] ===== CONTROL EXPERIMENT DONE ($SEQ) ====="
ls -la "$OUT"/*.tum 2>/dev/null
