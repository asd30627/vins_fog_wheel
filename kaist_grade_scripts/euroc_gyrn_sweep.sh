#!/usr/bin/env bash
# gyr_n sweet-spot sweep: MH_04 x {real, general_imu(f=1)} x gyr_n in {0.003,0.001,0.0003}.
# Find a gyr_n where general_imu grade is observable AND real ATE is not worse than stock.
# Endpoints already known: stock 0.01 (real 0.3951 / g1 0.3950) ; datasheet 0.00017 (real 0.4402 / g1 0.4554).
# Only changes the gyr_n config line; reuses cached gx1 bag; single VINS at a time. Wheel OFF.
# Writes gyrn_sweep.tsv only. Does NOT touch CARLA data.
set -o pipefail
SP=/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts
CFGDIR=/home/ivlab3/fwvio_estimator_ws_wheel/src/VINS-Fusion-ROS2-jazzy/config/euroc
SRC=$CFGDIR/euroc_stereo_imu_config.yaml
ROOT=/mnt/sata4t/ivlab3_data/fwvio/results/euroc_grade
B=/mnt/sata4t/datasets/EuRoC_full/ros2_bags
TSV=$ROOT/gyrn_sweep.tsv
seq=MH_04_difficult
GT=$ROOT/gt/${seq}_gt.tum
realbag=$B/$seq
g1bag=$ROOT/bags/${seq}__gx1
GYRNS=(0.003 0.001 0.0003)
[ -f "$TSV" ] || printf "gyr_n\tcell\trows\tATE\n" > "$TSV"
have(){ grep -qP "^$1\t$2\t" "$TSV"; }
for gn in "${GYRNS[@]}"; do
  tag=$(echo "$gn" | tr '.' 'p')
  cfg=$CFGDIR/euroc_stereo_imu_config_gyrn_${tag}.yaml
  [ -f "$cfg" ] || sed "s@^gyr_n: 0.01.*@gyr_n: ${gn}    # gyr_n sweep (stock 0.01)@" "$SRC" > "$cfg"
  if ! have "$gn" real; then
    line=$(bash $SP/euroc_grade_run.sh "$realbag" "$GT" "$seq" "sw${tag}_real" "$cfg" 2>/dev/null | grep EGRADE)
    echo "$line"
    rows=$(echo "$line"|grep -oE 'rows=[0-9]+'|cut -d= -f2); ate=$(echo "$line"|grep -oE 'ATE=[0-9.NA]+'|cut -d= -f2)
    printf "%s\treal\t%s\t%s\n" "$gn" "${rows:-0}" "${ate:-NA}" >> "$TSV"
  fi
  if ! have "$gn" general_imu; then
    line=$(bash $SP/euroc_grade_run.sh "$g1bag" "$GT" "$seq" "sw${tag}_g1" "$cfg" 2>/dev/null | grep EGRADE)
    echo "$line"
    rows=$(echo "$line"|grep -oE 'rows=[0-9]+'|cut -d= -f2); ate=$(echo "$line"|grep -oE 'ATE=[0-9.NA]+'|cut -d= -f2)
    printf "%s\tgeneral_imu\t%s\t%s\n" "$gn" "${rows:-0}" "${ate:-NA}" >> "$TSV"
  fi
done
echo "===== GYRN-SWEEP DONE $(date +%H:%M:%S) ====="
echo "(endpoints: stock gyr_n=0.01 real=0.3951 g1=0.3950 ; datasheet 0.00017 real=0.4402 g1=0.4554)"
column -t -s$'\t' "$TSV"
