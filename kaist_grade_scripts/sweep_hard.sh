#!/usr/bin/env bash
# Serial FOG-aided grade sweep over HARD KAIST seqs (isolation: one VINS at a time).
# Usage: sweep_hard.sh <seq1> [seq2 ...]   (grades: real + 3 injected, rep0)
SP=/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts
ROW=$SP/hard_grade_rows.tsv
[ -f "$ROW" ] || printf "seq\tgrade\tate_rmse\tvio_rows\twall_s\trc\n" > "$ROW"
GRADES="kaist_real_005 industrial_fog precision_mems general_imu"
for seq in "$@"; do
  for g in $GRADES; do
    # skip if already have a non-empty result row for this seq/grade
    out=$(bash "$SP/run_hard_one.sh" "$seq" "$g" 0 2>&1)
    echo "$out"
    line=$(echo "$out" | grep '\[hard\] ->')
    ate=$(echo "$line" | grep -oE 'ate=[^ ]+' | cut -d= -f2)
    rows=$(echo "$line" | grep -oE 'rows=[0-9]+' | cut -d= -f2)
    wall=$(echo "$line" | grep -oE 'wall=[0-9]+' | cut -d= -f2)
    rc=$(echo "$line" | grep -oE 'rc=[0-9]+' | cut -d= -f2)
    printf "%s\t%s\t%s\t%s\t%s\t%s\n" "$seq" "$g" "${ate:-NA}" "${rows:-0}" "${wall:-NA}" "${rc:-NA}" >> "$ROW"
  done
done
echo "===== SWEEP DONE $(date +%H:%M:%S) ====="
