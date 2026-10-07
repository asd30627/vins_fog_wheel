#!/usr/bin/env bash
# Knife-edge: scale the heaviest grade (general_imu) by f and find where ATE first moves.
# Anchored to VINS model gyr_n=0.01: injected white-noise std = 1.234e-3 * f, so observability
# floor is f~8 (injected wn ~= model gyr_n). Scan brackets the knife-edge geometrically.
# Reuses euroc_grade_run.sh (deterministic half-rate replay + Umeyama no-scale ATE).
# Writes a SEPARATE knife_matrix.tsv; never touches grade_matrix.tsv.
# Usage: bash euroc_knife_edge.sh [SEQ ...]   (default: MH_04_difficult)
set -o pipefail
SP=/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts
ROOT=/mnt/sata4t/ivlab3_data/fwvio/results/euroc_grade
B=/mnt/sata4t/datasets/EuRoC_full/ros2_bags
KTSV=$ROOT/knife_matrix.tsv
SCALES=(8 16 32 64)
SEQS=("$@"); [ ${#SEQS[@]} -eq 0 ] && SEQS=(MH_04_difficult)
[ -f "$KTSV" ] || printf "seq\tscale\twn_std\trows\tATE\n" > "$KTSV"
have(){ grep -qP "^$1\t$2\t" "$KTSV"; }
for seq in "${SEQS[@]}"; do
  # baseline real ATE for reference (copy from grade_matrix.tsv if present)
  for f in "${SCALES[@]}"; do
    if have "$seq" "$f"; then echo "[have] $seq x$f"; continue; fi
    bag="$ROOT/bags/${seq}__gx${f}"
    if [ ! -d "$bag" ]; then
      echo "[inject] $seq general_imu x$f"
      ( source /opt/ros/jazzy/setup.bash 2>/dev/null
        python3 $SP/inject_euroc_bag.py --bag "$B/$seq" --out "$bag" \
                --grade general_imu --scale "$f" --seed 42 ) 2>&1 | grep -E '\[inj\]|\[ok\]'
    fi
    wn=$(echo "scale=6; 0.001234*$f" | bc 2>/dev/null)
    line=$(bash $SP/euroc_grade_run.sh "$bag" "$ROOT/gt/${seq}_gt.tum" "$seq" "gx${f}" 2>/dev/null | grep EGRADE)
    echo "$line"
    rows=$(echo "$line"|grep -oE 'rows=[0-9]+'|cut -d= -f2)
    ate=$(echo "$line"|grep -oE 'ATE=[0-9.NA]+'|cut -d= -f2)
    printf "%s\t%s\t%s\t%s\t%s\n" "$seq" "$f" "${wn:-NA}" "${rows:-0}" "${ate:-NA}" >> "$KTSV"
  done
done
echo "===== KNIFE-EDGE DONE $(date +%H:%M:%S) ====="
column -t -s$'\t' "$KTSV"
