#!/usr/bin/env bash
# Run VINS-Fusion on an EuRoC ros2 bag (stereo+IMU), optional 15-dim IMU-cov oracle. Reports ATE vs GT.
# args: bagdir gt_tum tag oracle(0/1) [gt_override]
set -o pipefail   # NO 'set -u': sourcing ROS setup references unbound vars -> would exit early
bag="$1"; gt="$2"; tag="$3"; oracle="$4"; gtov="${5:-}"
WS=/home/ivlab3/fwvio_estimator_ws_wheel
CFGDIR=$WS/src/VINS-Fusion-ROS2-jazzy/config/euroc
RES=/mnt/sata4t/ivlab3_data/fwvio/results/euroc/$tag; mkdir -p "$RES"
TMPCFG="$CFGDIR/_tmp_${tag}.yaml"
sed "s#^output_path:.*#output_path: \"$RES/\"#" "$CFGDIR/euroc_stereo_imu_config.yaml" > "$TMPCFG"
source /opt/ros/jazzy/setup.bash 2>/dev/null; source "$WS/install/setup.bash" 2>/dev/null
if [ "$oracle" = 1 ]; then export REL_IMU_COV_ORACLE=1 REL_IMU_COV_ORACLE_GT="${gtov:-$gt}"; else unset REL_IMU_COV_ORACLE REL_IMU_COV_ORACLE_GT 2>/dev/null || true; fi
VINS="$WS/install/vins/lib/vins/vins_node"
rm -f "$RES/vio.csv"
"$VINS" "$TMPCFG" --ros-args > "$RES/vins.log" 2>&1 &
VPID=$!; sleep 6
ros2 bag play "$bag" --rate 0.5 > "$RES/play.log" 2>&1   # half-rate: VINS keeps up -> deterministic (no lag drop)
sleep 12; kill -INT "$VPID" 2>/dev/null; sleep 3; kill -9 "$VPID" 2>/dev/null
rm -f "$TMPCFG"
# vio.csv -> tum + ATE
/home/ivlab3/miniconda3/envs/gf/bin/python - "$RES/vio.csv" "$gt" <<'PY'
import sys,numpy as np,os
vp,gtp=sys.argv[1],sys.argv[2]
if not os.path.exists(vp) or os.path.getsize(vp)<100: print("  NO VIO (vins produced nothing)"); sys.exit()
v=np.loadtxt(vp,delimiter=",",usecols=range(8))  # ts,x,y,z,qw,qx,qy,qz
ts=v[:,0]; p=v[:,1:4]
g=np.loadtxt(gtp); gts=g[:,0]; gp=g[:,1:4]
idx=np.clip(np.searchsorted(gts,ts),0,len(gp)-1); s=p; d=gp[idx]
ms,md=s.mean(0),d.mean(0);S=s-ms;Dd=d-md;C=Dd.T@S/len(s);U,_,Vt=np.linalg.svd(C);R=U@Vt
if np.linalg.det(R)<0:U[:,-1]*=-1;R=U@Vt
ate=np.sqrt((((R@s.T).T+(md-R@ms)-d)**2).sum(1).mean())
print(f"  rows={len(v)} ATE={ate:.4f}m")
# also write vio.tum (ts x y z qx qy qz qw) for alignment
tum=np.column_stack([ts,p[:,0],p[:,1],p[:,2],v[:,5],v[:,6],v[:,7],v[:,4]])
np.savetxt(os.path.dirname(vp)+"/vio.tum",tum,fmt="%.9f")
PY
grep -c "IMU_COV_ORACLE\] loaded" "$RES/vins.log" 2>/dev/null | sed 's/^/  oracle_loaded=/'
