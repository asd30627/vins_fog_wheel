#!/usr/bin/env bash
# Run ONE KAIST seq as PURE stereo+xsens VIO (CONFIG_MODE=imu: xsens IMU, NO FOG, NO wheel).
# KAIST GT = iSAM(FOG+wheel+RTK) does NOT contain camera or xsens -> clean oracle platform.
# Optional 15-dim IMU-cov oracle (aligned GT). Reports rows, completion%, ATE.
# args: seq tag oracle(0/1) [gt_override_tum] [imu_csv_override_relpath]
set -uo pipefail
seq="$1"; tag="$2"; oracle="${3:-0}"; gtov="${4:-}"; imucsv="${5:-}"
WS=/home/ivlab3/fwvio_estimator_ws
WBIN=/home/ivlab3/fwvio_estimator_ws_wheel/install/vins/lib/vins/vins_node
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
SP=/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts
GF=/home/ivlab3/miniconda3/envs/gf/bin/python
TEMPLATE="$WS/src/kaist_player/config/kaist_xsens_vio.yaml"   # pure xsens VIO (imu_source inside block)
GT="$EXT/$seq/pose/$seq/global_pose.tum"
OUT=/mnt/sata4t/ivlab3_data/fwvio/results/kaist_vio
dst="$OUT/$seq/$tag"; mkdir -p "$dst"

export VINS_BIN_OVERRIDE="$WBIN"
# pure VIO: no wheel
unset WHEEL_FACTOR_ENABLE WHEEL_MODE REL_WHEEL_PRELOAD 2>/dev/null || true
if [ "$oracle" = 1 ]; then export REL_IMU_COV_ORACLE=1 REL_IMU_COV_ORACLE_GT="${gtov:-$GT}";
else unset REL_IMU_COV_ORACLE REL_IMU_COV_ORACLE_GT 2>/dev/null || true; fi
# optional degraded xsens csv override (step 3); relpath under seq root
[ -n "$imucsv" ] && export IMU_CSV_OVERRIDE="$imucsv" || unset IMU_CSV_OVERRIDE 2>/dev/null || true

t0=$(date +%s)
cd "$WS"
GRADE=kaist_real_005 USE_EXPLICIT_FIXEDEXT=0 IMU_CSV_OVERRIDE="${imucsv}" \
  bash scripts/run_one_p1_baseline.sh "$seq" "$EXT/$seq" "$TEMPLATE" "$GT" imu \
  > "$dst/runner.log" 2>&1
rc=$?; wall=$(($(date +%s)-t0))
src="/mnt/sata4t/ivlab3_data/fwvio/results/p1_factors/_work/imu/$seq"
cp -f "$src/vins_raw/vio.tum" "$dst/" 2>/dev/null
cp -f "$src/logs/vins.log" "$dst/vins.log" 2>/dev/null
cp -f "$src/logs/player.log" "$dst/player.log" 2>/dev/null

$GF - "$seq" "$dst" "$GT" <<'PY'
import numpy as np,os,sys
seq,dst,gtp=sys.argv[1],sys.argv[2],sys.argv[3]
vt=f"{dst}/vio.tum"
if not os.path.exists(vt) or os.path.getsize(vt)<100: print(f"RESULT {seq}: rows=0 completion=0% ATE=NA"); sys.exit()
v=np.loadtxt(vt);
if v.ndim==1: print(f"RESULT {seq}: rows=1 completion=0% ATE=NA"); sys.exit()
ts=v[:,0]; p=v[:,1:4]
g=np.loadtxt(gtp); gts=g[:,0]; gp=g[:,1:4]
gdur=gts[-1]-gts[0]; vdur=ts[-1]-ts[0]
comp=100.0*vdur/gdur if gdur>0 else 0
idx=np.clip(np.searchsorted(gts,ts),0,len(gp)-1); s=p; d=gp[idx]
ms,md=s.mean(0),d.mean(0);S=s-ms;Dd=d-md;C=Dd.T@S/len(s);U,_,Vt=np.linalg.svd(C);R=U@Vt
if np.linalg.det(R)<0:U[:,-1]*=-1;R=U@Vt
ate=np.sqrt((((R@s.T).T+(md-R@ms)-d)**2).sum(1).mean())
print(f"RESULT {seq}: rows={len(v)} completion={comp:.1f}% ATE={ate:.3f}m vdur={vdur:.0f}s gdur={gdur:.0f}s")
PY
echo "  [rc=$rc wall=${wall}s oracle=$oracle] $(grep -c 'IMU_COV_ORACLE\] loaded' "$dst/vins.log" 2>/dev/null|sed 's/^/oracle_loaded_msg=/')"
