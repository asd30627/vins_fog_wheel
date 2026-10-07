#!/usr/bin/env bash
# Step 3: xsens IMU degradation sweep. For representative usable seqs, inject 3 grades onto xsens gyro
# and measure oracle improvement vs degradation level. Pure VIO (xsens, no FOG/wheel).
# Per (seq, grade): degraded baseline -> align GT -> degraded+oracle. Plus real grade (reuse step1/step2).
# args: optional space-separated seq list (default: representative mixed-sign subset).
set -uo pipefail
SP=/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts
GF=/home/ivlab3/miniconda3/envs/gf/bin/python
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
OUT=/mnt/sata4t/ivlab3_data/fwvio/results/kaist_vio
TSV=$SP/kaist_grade_step3.tsv
GRADES=(industrial_fog precision_mems general_imu)
SEQS=(${@:-urban29-pankyo urban37-seoul urban26-dongtan urban35-seoul})
printf "seq\tgrade\tbase_ATE\toracle_ATE\timprove%%\n" > "$TSV"

ate_of_tum(){ # vio.tum gt.tum
  $GF - "$1" "$2" <<'PY'
import numpy as np,sys,os
vt,gt=sys.argv[1],sys.argv[2]
if not os.path.exists(vt) or os.path.getsize(vt)<100: print("NA"); sys.exit()
v=np.loadtxt(vt); g=np.loadtxt(gt)
if v.ndim==1: print("NA"); sys.exit()
ts=v[:,0]; p=v[:,1:4]; gts=g[:,0]; gp=g[:,1:4]
idx=np.clip(np.searchsorted(gts,ts),0,len(gp)-1); s=p; d=gp[idx]
ms,md=s.mean(0),d.mean(0);S=s-ms;Dd=d-md;C=Dd.T@S/len(s);U,_,Vt=np.linalg.svd(C);R=U@Vt
if np.linalg.det(R)<0:U[:,-1]*=-1;R=U@Vt
print(f"{np.sqrt((((R@s.T).T+(md-R@ms)-d)**2).sum(1).mean()):.3f}")
PY
}
imp_of(){ $GF -c "b='$1';o='$2';print('%.1f'%(100*(float(b)-float(o))/float(b)) if (b and o and b!='NA' and o!='NA' and float(b)>0) else 'NA')" 2>/dev/null; }

for seq in "${SEQS[@]}"; do
  GT="$EXT/$seq/pose/$seq/global_pose.tum"
  # --- real grade row: reuse step1 base + step2 oracle ---
  rb=$(ate_of_tum "$OUT/$seq/base/vio.tum" "$GT")
  ro=$(ate_of_tum "$OUT/$seq/orac/vio.tum" "$GT")
  printf "%s\t%s\t%s\t%s\t%s\n" "$seq" "kaist_real_005" "$rb" "$ro" "$(imp_of "$rb" "$ro")" >> "$TSV"
  echo "GSWEEP $seq real: base=$rb oracle=$ro improve=$(imp_of "$rb" "$ro")%"
  # --- 3 injected grades ---
  for g in "${GRADES[@]}"; do
    $GF "$SP/gen_kaist_grade_xsens.py" --seq "$seq" --grade "$g" > "$SP/gx_${seq}_${g}.log" 2>&1
    rel="data/$seq/sensor_data/xsens_grade_${g}.csv"
    # degraded baseline (no oracle)
    bash "$SP/kaist_vio_one.sh" "$seq" "g_${g}_base" 0 "" "$rel" > "$SP/gsw_${seq}_${g}_base.log" 2>&1
    bvt="$OUT/$seq/g_${g}_base/vio.tum"; gb=$(ate_of_tum "$bvt" "$GT")
    # align GT to degraded baseline
    ALG="$OUT/$seq/g_${g}_aligned_gt.tum"
    $GF "$SP/align_gt.py" "$bvt" "$GT" "$ALG" > "$SP/gsw_${seq}_${g}_align.log" 2>&1
    # degraded + oracle
    bash "$SP/kaist_vio_one.sh" "$seq" "g_${g}_orac" 1 "$ALG" "$rel" > "$SP/gsw_${seq}_${g}_orac.log" 2>&1
    go=$(ate_of_tum "$OUT/$seq/g_${g}_orac/vio.tum" "$GT")
    printf "%s\t%s\t%s\t%s\t%s\n" "$seq" "$g" "$gb" "$go" "$(imp_of "$gb" "$go")" >> "$TSV"
    echo "GSWEEP $seq $g: base=$gb oracle=$go improve=$(imp_of "$gb" "$go")%"
  done
done
echo "===== KAIST_GRADE_STEP3_DONE $(date +%H:%M:%S) ====="
column -t -s$'\t' "$TSV"
