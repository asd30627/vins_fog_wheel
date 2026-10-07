#!/usr/bin/env bash
# Physics-vs-config knife-edge: re-run MH_04 knife scan under a DATASHEET-tuned VINS config
# (gyr_n = ADIS16448 1.6968e-4 instead of stock 0.01). Same gyro-injected bags, only config differs.
# Cells: real + general_imu x{1,2,4,8}. Single VINS at a time. Wheel OFF (pure stereo-IMU VIO).
# Writes knife_tuned_matrix.tsv; never touches grade_matrix.tsv / knife_matrix.tsv.
set -o pipefail
SP=/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts
CFGDIR=/home/ivlab3/fwvio_estimator_ws_wheel/src/VINS-Fusion-ROS2-jazzy/config/euroc
TUNED=$CFGDIR/euroc_stereo_imu_config_gyrn_ds.yaml
ROOT=/mnt/sata4t/ivlab3_data/fwvio/results/euroc_grade
B=/mnt/sata4t/datasets/EuRoC_full/ros2_bags
KTSV=$ROOT/knife_tuned_matrix.tsv
seq=MH_04_difficult
SCALES=(1 2 4 8)
[ -f "$KTSV" ] || printf "seq\tcfg\tscale\twn_std\trows\tATE\n" > "$KTSV"
have(){ grep -qP "^$seq\t$1\t$2\t" "$KTSV"; }

# --- real baseline under tuned config ---
if ! have ds_real 0; then
  line=$(bash $SP/euroc_grade_run.sh "$B/$seq" "$ROOT/gt/${seq}_gt.tum" "$seq" "ds_real" "$TUNED" 2>/dev/null | grep EGRADE)
  echo "$line"
  rows=$(echo "$line"|grep -oE 'rows=[0-9]+'|cut -d= -f2); ate=$(echo "$line"|grep -oE 'ATE=[0-9.NA]+'|cut -d= -f2)
  printf "%s\tds\t0\t0\t%s\t%s\n" "$seq" "${rows:-0}" "${ate:-NA}" >> "$KTSV"
fi

# --- general_imu x{1,2,4,8} under tuned config (reuse cached bags where present) ---
for f in "${SCALES[@]}"; do
  if have ds "$f"; then echo "[have] $seq ds x$f"; continue; fi
  bag="$ROOT/bags/${seq}__gx${f}"
  if [ ! -d "$bag" ]; then
    echo "[inject] $seq general_imu x$f"
    ( source /opt/ros/jazzy/setup.bash 2>/dev/null
      python3 $SP/inject_euroc_bag.py --bag "$B/$seq" --out "$bag" --grade general_imu --scale "$f" --seed 42 ) \
      2>&1 | grep -E '\[inj\]|\[ok\]'
  fi
  wn=$(echo "scale=6; 0.001234*$f" | bc 2>/dev/null)
  line=$(bash $SP/euroc_grade_run.sh "$bag" "$ROOT/gt/${seq}_gt.tum" "$seq" "ds_gx${f}" "$TUNED" 2>/dev/null | grep EGRADE)
  echo "$line"
  rows=$(echo "$line"|grep -oE 'rows=[0-9]+'|cut -d= -f2); ate=$(echo "$line"|grep -oE 'ATE=[0-9.NA]+'|cut -d= -f2)
  printf "%s\tds\t%s\t%s\t%s\t%s\n" "$seq" "$f" "${wn:-NA}" "${rows:-0}" "${ate:-NA}" >> "$KTSV"
done
echo "===== KNIFE-TUNED DONE $(date +%H:%M:%S) ====="
echo "(compare against STOCK-config knife: f1=0.3950 f8=0.4397 ... real_stock=0.3951)"
column -t -s$'\t' "$KTSV"
