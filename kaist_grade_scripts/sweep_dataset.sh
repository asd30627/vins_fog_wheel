#!/usr/bin/env bash
# Full reliability-dataset re-run: 12 seq x 4 grade x rep0, serial isolated, WITH reliability CSV copy.
# Uses run_hard_one.sh (already patched to cp reliability_features.csv -> dst). NO estimator change.
SP=/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts
ROW=$SP/dataset_rows.tsv
[ -f "$ROW" ] || printf "seq\tgrade\tate\trows\twall\trc\tcsv_rows\n" > "$ROW"
GRADES="kaist_real_005 industrial_fog precision_mems general_imu"
SEQS="$@"
for seq in $SEQS; do
  for g in $GRADES; do
    out=$(bash "$SP/run_hard_one.sh" "$seq" "$g" 0 2>&1); echo "$out"
    line=$(echo "$out" | grep '\[hard\] ->')
    ate=$(echo "$line"|grep -oE 'ate=[^ ]+'|cut -d= -f2); rows=$(echo "$line"|grep -oE 'rows=[0-9]+'|cut -d= -f2)
    wall=$(echo "$line"|grep -oE 'wall=[0-9]+'|cut -d= -f2); rc=$(echo "$line"|grep -oE 'rc=[0-9]+'|cut -d= -f2)
    csv="$SP/../../../../mnt/sata4t/ivlab3_data/fwvio/results/p1_grade_hard/$seq/${g}_rep0/reliability_features.csv"
    cr=$(wc -l < "/mnt/sata4t/ivlab3_data/fwvio/results/p1_grade_hard/$seq/${g}_rep0/reliability_features.csv" 2>/dev/null || echo 0)
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$seq" "$g" "${ate:-NA}" "${rows:-0}" "${wall:-NA}" "${rc:-NA}" "$cr" >> "$ROW"
  done
done
echo "===== DATASET SWEEP DONE $(date +%H:%M:%S) ====="
