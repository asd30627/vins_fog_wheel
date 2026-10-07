#!/usr/bin/env bash
# Representative 4-config table: 5 seqs x real grade x {wheel 0/1} x {baseline, 15-dim oracle}.
SP=/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts
ROW=$SP/oracle_sweep_rows.tsv
printf "wheel\tseq\tgrade\tATE_base\tATE_oracle\timprove%%\n" > "$ROW"
SEQS=(urban26-dongtan urban27-dongtan urban28-pankyo urban29-pankyo urban38-pankyo)
ateof(){ grep -oE 'ATE=[0-9.]+' "$1" 2>/dev/null | tail -1 | cut -d= -f2; }
for wheel in 0 1; do
  for seq in "${SEQS[@]}"; do
    bash $SP/oracle_run.sh "$seq" kaist_real_005 "swb_w${wheel}" 0 "$wheel" > "$SP/swr_${seq}_w${wheel}_base.log" 2>&1
    ab=$(ateof "$SP/swr_${seq}_w${wheel}_base.log")
    bash $SP/oracle_run.sh "$seq" kaist_real_005 "swo_w${wheel}" 1 "$wheel" > "$SP/swr_${seq}_w${wheel}_orac.log" 2>&1
    ao=$(ateof "$SP/swr_${seq}_w${wheel}_orac.log")
    imp=$(/home/ivlab3/miniconda3/envs/gf/bin/python -c "b='$ab';o='$ao';print('%.1f'%(100*(float(b)-float(o))/float(b)) if (b and o and float(b)>0) else 'NA')" 2>/dev/null)
    printf "%s\t%s\treal\t%s\t%s\t%s\n" "$wheel" "$seq" "${ab:-NA}" "${ao:-NA}" "${imp:-NA}" >> "$ROW"
    echo "  [w$wheel] $seq base=$ab oracle=$ao improve=$imp%"
  done
done
echo "===== REP SWEEP DONE $(date +%H:%M:%S) ====="
