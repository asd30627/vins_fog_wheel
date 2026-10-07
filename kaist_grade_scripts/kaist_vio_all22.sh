#!/usr/bin/env bash
# Step 1: run all KAIST urban18-39 stereo seqs as pure stereo+xsens VIO (real grade).
# Reports seq | vio_rows | completion% | ATE_m | usable(>80%)? into a TSV.
set -o pipefail
SP=/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
TSV=$SP/kaist_vio_step1.tsv
printf "seq\trows\tcompletion%%\tATE_m\tusable\n" > "$TSV"
SEQS=()
for n in $(seq 18 39); do d=$(ls -d "$EXT"/urban${n}-* 2>/dev/null|head -1); [ -n "$d" ] && SEQS+=("$(basename "$d")"); done
echo "step1 seqs: ${SEQS[*]}"
for seq in "${SEQS[@]}"; do
  line=$(bash "$SP/kaist_vio_one.sh" "$seq" base 0 2>/dev/null | grep '^RESULT')
  echo "$line"
  rows=$(echo "$line"|grep -oE 'rows=[0-9]+'|cut -d= -f2)
  comp=$(echo "$line"|grep -oE 'completion=[0-9.]+'|cut -d= -f2)
  ate=$(echo "$line"|grep -oE 'ATE=[0-9.NA]+'|cut -d= -f2)
  use=$(/home/ivlab3/miniconda3/envs/gf/bin/python -c "c='$comp';print('YES' if (c and float(c)>80) else 'no')" 2>/dev/null)
  printf "%s\t%s\t%s\t%s\t%s\n" "$seq" "${rows:-0}" "${comp:-0}" "${ate:-NA}" "${use:-no}" >> "$TSV"
done
echo "===== KAIST_VIO_STEP1_DONE $(date +%H:%M:%S) ====="
column -t -s$'\t' "$TSV"
