#!/usr/bin/env bash
# IMU-cov-oracle ceiling: 4 configs = {wheel 0/1} x {easy urban26-29, marginal urban38}.
# Per (seq,grade,wheel): run baseline(oracle0) + oracle(oracle1) with SAME binary -> isolate oracle effect.
# failureDetection already disabled (return false). Serial isolated (CARLA off).
SP=/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts
ROW=$SP/oracle_sweep_rows.tsv
EASY=(urban26-dongtan urban27-dongtan urban28-pankyo urban29-pankyo)
MARG=(urban38-pankyo)
GRADES=(kaist_real_005 industrial_fog precision_mems general_imu)
[ -f "$ROW" ] || printf "wheel\tseq\tgrade\tATE_base\tATE_oracle\timprove%%\n" > "$ROW"
ateof(){ grep -oE 'ATE=[0-9.]+' "$1" 2>/dev/null | tail -1 | cut -d= -f2; }
run_pair(){ # wheel seq grade
  local wheel="$1" seq="$2" grade="$3"
  local tagb="orB_w${wheel}" tago="orO_w${wheel}"
  bash "$SP/oracle_run.sh" "$seq" "$grade" "$tagb" 0 "$wheel" > "$SP/sw_${seq}_${grade}_w${wheel}_base.log" 2>&1
  local ab=$(ateof "$SP/sw_${seq}_${grade}_w${wheel}_base.log")
  bash "$SP/oracle_run.sh" "$seq" "$grade" "$tago" 1 "$wheel" > "$SP/sw_${seq}_${grade}_w${wheel}_orac.log" 2>&1
  local ao=$(ateof "$SP/sw_${seq}_${grade}_w${wheel}_orac.log")
  local imp=$(/home/ivlab3/miniconda3/envs/gf/bin/python -c "b='$ab';o='$ao'; print('%.1f'%(100*(float(b)-float(o))/float(b)) if (b and o and float(b)>0) else 'NA')" 2>/dev/null)
  printf "%s\t%s\t%s\t%s\t%s\t%s\n" "$wheel" "$seq" "$grade" "${ab:-NA}" "${ao:-NA}" "${imp:-NA}" >> "$ROW"
  echo "  [w$wheel] $seq/$grade base=$ab oracle=$ao improve=$imp%"
}
for wheel in 0 1; do
  echo "===== CONFIG wheel=$wheel $(date +%H:%M:%S) ====="
  for seq in "${EASY[@]}" "${MARG[@]}"; do
    for g in "${GRADES[@]}"; do run_pair "$wheel" "$seq" "$g"; done
  done
done
echo "===== ORACLE SWEEP DONE $(date +%H:%M:%S) ====="
