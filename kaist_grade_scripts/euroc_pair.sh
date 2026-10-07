#!/usr/bin/env bash
# EuRoC paired: baseline -> align GT to baseline vio -> 15-dim oracle with aligned GT. args: bagdir gt_tum name
set -uo pipefail
bag="$1"; gt="$2"; name="$3"
SP=/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts
GF=/home/ivlab3/miniconda3/envs/gf/bin/python
RESROOT=/mnt/sata4t/ivlab3_data/fwvio/results/euroc
ateof(){ grep -oE 'ATE=[0-9.]+' "$1" 2>/dev/null | tail -1 | cut -d= -f2; }
# baseline
bash "$SP/euroc_run.sh" "$bag" "$gt" "${name}_base" 0 > "$SP/euroc_${name}_base.log" 2>&1
ab=$(ateof "$SP/euroc_${name}_base.log")
# align
ALG="$RESROOT/${name}_aligned_gt.tum"
$GF "$SP/align_gt.py" "$RESROOT/${name}_base/vio.tum" "$gt" "$ALG" > "$SP/euroc_${name}_align.log" 2>&1
# oracle with aligned GT
bash "$SP/euroc_run.sh" "$bag" "$gt" "${name}_orac" 1 "$ALG" > "$SP/euroc_${name}_orac.log" 2>&1
ao=$(ateof "$SP/euroc_${name}_orac.log")
imp=$($GF -c "b='$ab';o='$ao';print('%.1f'%(100*(float(b)-float(o))/float(b)) if (b and o and float(b)>0) else 'NA')" 2>/dev/null)
echo "EUROC $name: base=$ab oracle_aligned=$ao improve=$imp% (align $(grep -oE 'align_rmse=[0-9.]+' "$SP/euroc_${name}_align.log"))"
