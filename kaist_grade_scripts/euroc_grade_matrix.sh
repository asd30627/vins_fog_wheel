#!/usr/bin/env bash
# Full EuRoC grade-sensitivity matrix: 11 seq x {real, industrial_fog, precision_mems, general_imu}.
# Injects degraded bags (gyro-only, KAIST PROFILES) then runs VINS + ATE. Resumable.
set -o pipefail
SP=/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts
ROOT=/mnt/sata4t/ivlab3_data/fwvio/results/euroc_grade
B=/mnt/sata4t/datasets/EuRoC_full/ros2_bags
TSV=$ROOT/grade_matrix.tsv
# Reordered 2026-06-29: hard sequences FIRST, and within each seq baseline+heaviest first,
# so the decisive grade-interaction cells (hard x {real, general_imu}) surface early.
# Same 44 cells, same seed=42, resumable -- pure scheduling change, no scientific change.
SEQS=(MH_04_difficult MH_05_difficult V1_03_difficult V2_03_difficult \
      MH_03_medium V1_02_medium V2_02_medium \
      MH_01_easy MH_02_easy V1_01_easy V2_01_easy)
GRADES=(real general_imu industrial_fog precision_mems)
[ -f "$TSV" ] || printf "seq\tgrade\trows\tATE\n" > "$TSV"
already(){ grep -qP "^$1\t$2\t" "$TSV"; }
for seq in "${SEQS[@]}"; do
  for grade in "${GRADES[@]}"; do
    if already "$seq" "$grade"; then echo "[have] $seq $grade"; continue; fi
    if [ "$grade" = real ]; then bag="$B/$seq"; else
      bag="$ROOT/bags/${seq}__${grade}"
      if [ ! -d "$bag" ]; then
        echo "[inject] $seq $grade"
        ( source /opt/ros/jazzy/setup.bash 2>/dev/null
          python3 $SP/inject_euroc_bag.py --bag "$B/$seq" --out "$bag" --grade "$grade" --seed 42 ) \
          2>&1 | grep -E '\[inj\]|\[ok\]'
      fi
    fi
    line=$(bash $SP/euroc_grade_run.sh "$bag" "$ROOT/gt/${seq}_gt.tum" "$seq" "$grade" 2>/dev/null | grep EGRADE)
    echo "$line"
    rows=$(echo "$line"|grep -oE 'rows=[0-9]+'|cut -d= -f2)
    ate=$(echo "$line"|grep -oE 'ATE=[0-9.NA]+'|cut -d= -f2)
    printf "%s\t%s\t%s\t%s\n" "$seq" "$grade" "${rows:-0}" "${ate:-NA}" >> "$TSV"
  done
done
echo "===== MATRIX DONE $(date +%H:%M:%S) ====="
column -t -s$'\t' "$TSV"
