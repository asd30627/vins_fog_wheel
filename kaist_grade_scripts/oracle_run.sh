#!/usr/bin/env bash
# Run ONE KAIST seq/grade with IMU-cov-oracle ON or OFF, wheel ON or OFF. Reports ATE+early/late.
# args: seq grade rep(tag) oracle(0/1) wheel(0/1)
set -uo pipefail
seq="$1" grade="$2" rep="$3" oracle="$4" wheel="$5"
WBIN=/home/ivlab3/fwvio_estimator_ws_wheel/install/vins/lib/vins/vins_node
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
P1H=/mnt/sata4t/ivlab3_data/fwvio/results/p1_grade_hard
SP=/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts
GF=/home/ivlab3/miniconda3/envs/gf/bin/python
GT="$EXT/$seq/pose/$seq/global_pose.tum"
export VINS_BIN_OVERRIDE="$WBIN"
if [ "$oracle" = 1 ]; then export REL_IMU_COV_ORACLE=1 REL_IMU_COV_ORACLE_GT="${GT_OVERRIDE:-$GT}"; else unset REL_IMU_COV_ORACLE REL_IMU_COV_ORACLE_GT; fi
if [ "$wheel" = 1 ]; then
  # generate KAIST wheel CSV from encoder, preload
  $GF "$SP/gen_kaist_wheel.py" "$seq" >/dev/null 2>&1
  export WHEEL_FACTOR_ENABLE=1 WHEEL_MODE=se2 REL_WHEEL_PRELOAD="$EXT/$seq/data/$seq/sensor_data/kaist_wheel.csv"
else unset WHEEL_FACTOR_ENABLE WHEEL_MODE REL_WHEEL_PRELOAD; fi
bash "$SP/run_hard_one.sh" "$seq" "$grade" "$rep" > "$SP/oracle_${seq}_${grade}_${rep}.log" 2>&1
D="$P1H/$seq/${grade}_rep${rep}"
$GF - "$seq" "$D" <<PY
import numpy as np,os,sys
seq="$seq"; D="$D"; EXT="$EXT"
vt=f"{D}/vio.tum"
if not os.path.exists(vt) or os.path.getsize(vt)<100: print("  NO VIO"); sys.exit()
v=np.loadtxt(vt); ts=v[:,0]; p=v[:,1:4]
gt=np.loadtxt(f"{EXT}/{seq}/pose/{seq}/global_pose.tum"); gts=gt[:,0]; gp=gt[:,1:4]
idx=np.clip(np.searchsorted(gts,ts),0,len(gp)-1); s=p; d=gp[idx]
ms,md=s.mean(0),d.mean(0);S=s-ms;Dd=d-md;C=Dd.T@S/len(s);U,_,Vt=np.linalg.svd(C);R=U@Vt
if np.linalg.det(R)<0:U[:,-1]*=-1;R=U@Vt
ate=np.sqrt((((R@s.T).T+(md-R@ms)-d)**2).sum(1)).mean()
print(f"  rows={len(v)} ATE={ate:.3f}m")
PY
grep -c "IMU_COV_ORACLE\] loaded" "$D/vins.log" 2>/dev/null | sed 's/^/  oracle_loaded_msg=/'
