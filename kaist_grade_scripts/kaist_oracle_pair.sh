#!/usr/bin/env bash
# Step 2: ONE KAIST seq paired baseline -> align GT to baseline vio -> 15-dim aligned-GT oracle.
# Pure VIO (xsens, no FOG/wheel). Reuses step-1 baseline if present. args: seq
set -uo pipefail
seq="$1"
SP=/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts
GF=/home/ivlab3/miniconda3/envs/gf/bin/python
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
OUT=/mnt/sata4t/ivlab3_data/fwvio/results/kaist_vio
GT="$EXT/$seq/pose/$seq/global_pose.tum"
ateof(){ grep -oE 'ATE=[0-9.]+' "$1" 2>/dev/null | tail -1 | cut -d= -f2; }

# baseline (reuse step-1 if vio.tum exists, else run)
bvt="$OUT/$seq/base/vio.tum"
if [ ! -s "$bvt" ]; then
  bash "$SP/kaist_vio_one.sh" "$seq" base 0 > "$SP/kor_${seq}_base.log" 2>&1
fi
ab=$($GF - "$bvt" "$GT" <<'PY'
import numpy as np,sys,os
vt,gt=sys.argv[1],sys.argv[2]
if not os.path.exists(vt): print("NA"); sys.exit()
v=np.loadtxt(vt); g=np.loadtxt(gt); ts=v[:,0]; p=v[:,1:4]; gts=g[:,0]; gp=g[:,1:4]
idx=np.clip(np.searchsorted(gts,ts),0,len(gp)-1); s=p; d=gp[idx]
ms,md=s.mean(0),d.mean(0);S=s-ms;Dd=d-md;C=Dd.T@S/len(s);U,_,Vt=np.linalg.svd(C);R=U@Vt
if np.linalg.det(R)<0:U[:,-1]*=-1;R=U@Vt
print(f"{np.sqrt((((R@s.T).T+(md-R@ms)-d)**2).sum(1).mean()):.3f}")
PY
)
# align GT to baseline vio
ALG="$OUT/$seq/aligned_gt.tum"
$GF "$SP/align_gt.py" "$bvt" "$GT" "$ALG" > "$SP/kor_${seq}_align.log" 2>&1
# oracle with aligned GT
bash "$SP/kaist_vio_one.sh" "$seq" orac 1 "$ALG" > "$SP/kor_${seq}_orac.log" 2>&1
ao=$(grep -oE 'ATE=[0-9.]+' "$SP/kor_${seq}_orac.log" 2>/dev/null | tail -1 | cut -d= -f2)
imp=$($GF -c "b='$ab';o='$ao';print('%.1f'%(100*(float(b)-float(o))/float(b)) if (b and o and b!='NA' and float(b)>0) else 'NA')" 2>/dev/null)
arm=$(grep -oE 'align_rmse=[0-9.]+' "$SP/kor_${seq}_align.log" | head -1)
echo "KORACLE $seq: base=$ab oracle=$ao improve=$imp% ($arm)"
