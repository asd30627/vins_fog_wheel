#!/usr/bin/env bash
# Paired run for the 15-dim IMU-cov oracle WITH frame-aligned GT:
#   1) baseline (oracle off) -> vio.tum  2) align raw GT to baseline vio (SE3 Umeyama)  3) oracle with aligned GT.
# args: seq grade wheel   -> echoes base ATE, oracle ATE, improve%
set -uo pipefail
seq="$1" grade="$2" wheel="$3"
SP=/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts
GF=/home/ivlab3/miniconda3/envs/gf/bin/python
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
P1H=/mnt/sata4t/ivlab3_data/fwvio/results/p1_grade_hard
RAWGT="$EXT/$seq/pose/$seq/global_pose.tum"
ateof(){ grep -oE 'ATE=[0-9.]+' "$1" 2>/dev/null | tail -1 | cut -d= -f2; }
# 1) baseline
bash "$SP/oracle_run.sh" "$seq" "$grade" "pB_w${wheel}" 0 "$wheel" > "$SP/pair_${seq}_${grade}_w${wheel}_base.log" 2>&1
ab=$(ateof "$SP/pair_${seq}_${grade}_w${wheel}_base.log")
# 2) align GT to baseline vio
VIO="$P1H/$seq/${grade}_reppB_w${wheel}/vio.tum"
ALG="$P1H/$seq/${grade}_aligned_gt_w${wheel}.tum"
$GF "$SP/align_gt.py" "$VIO" "$RAWGT" "$ALG" > "$SP/pair_${seq}_${grade}_w${wheel}_align.log" 2>&1
# 3) oracle with aligned GT
GT_OVERRIDE="$ALG" bash "$SP/oracle_run.sh" "$seq" "$grade" "pO_w${wheel}" 1 "$wheel" > "$SP/pair_${seq}_${grade}_w${wheel}_orac.log" 2>&1
ao=$(ateof "$SP/pair_${seq}_${grade}_w${wheel}_orac.log")
imp=$($GF -c "b='$ab';o='$ao';print('%.1f'%(100*(float(b)-float(o))/float(b)) if (b and o and float(b)>0) else 'NA')" 2>/dev/null)
echo "PAIR $seq/$grade w$wheel: base=$ab oracle_aligned=$ao improve=$imp% (align: $(grep -oE 'align_rmse=[0-9.]+' "$SP/pair_${seq}_${grade}_w${wheel}_align.log"))"
