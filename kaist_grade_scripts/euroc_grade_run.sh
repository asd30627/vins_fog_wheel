#!/usr/bin/env bash
# Run VINS-Fusion on an EuRoC bag (real or grade-degraded), compute ATE vs GT (Umeyama, no scale).
# Captures reliability_features_vins.csv for visual proxies. Deterministic: half-rate single-bag replay.
# args: <bagdir> <gt_tum> <seq> <grade> [base_cfg]   (grade=real means original bag)
#   base_cfg optional: path to a VINS config to use (default = stock euroc_stereo_imu_config.yaml)
set -o pipefail
bag="$1"; gt="$2"; seq="$3"; grade="$4"
WS=/home/ivlab3/fwvio_estimator_ws_wheel
CFGDIR=$WS/src/VINS-Fusion-ROS2-jazzy/config/euroc
BASECFG="${5:-$CFGDIR/euroc_stereo_imu_config.yaml}"
ROOT=/mnt/sata4t/ivlab3_data/fwvio/results/euroc_grade
RES=$ROOT/runs/${seq}__${grade}; mkdir -p "$RES"
TMPCFG="$CFGDIR/_tmpg_${seq}_${grade}.yaml"
sed "s#^output_path:.*#output_path: \"$RES/\"#" "$BASECFG" > "$TMPCFG"
source /opt/ros/jazzy/setup.bash 2>/dev/null; source "$WS/install/setup.bash" 2>/dev/null
unset REL_IMU_COV_ORACLE REL_IMU_COV_ORACLE_GT 2>/dev/null || true
VINS="$WS/install/vins/lib/vins/vins_node"
rm -f "$RES/vio.csv" /tmp/reliability_features_vins.csv
"$VINS" "$TMPCFG" --ros-args > "$RES/vins.log" 2>&1 &
VPID=$!; sleep 6
ros2 bag play "$bag" --rate 0.5 > "$RES/play.log" 2>&1
sleep 12; kill -INT "$VPID" 2>/dev/null; sleep 3; kill -9 "$VPID" 2>/dev/null
rm -f "$TMPCFG"
[ -f /tmp/reliability_features_vins.csv ] && cp /tmp/reliability_features_vins.csv "$RES/reliability_features_vins.csv"
/home/ivlab3/miniconda3/envs/gf/bin/python - "$RES/vio.csv" "$gt" "$seq" "$grade" <<'PY'
import sys,numpy as np,os
vp,gtp,seq,grade=sys.argv[1:5]
if not os.path.exists(vp) or os.path.getsize(vp)<100:
    print(f"EGRADE {seq} {grade}: rows=0 ATE=NA CRASH"); sys.exit()
v=np.loadtxt(vp,delimiter=",",usecols=range(8))
if v.ndim==1: v=v[None,:]
ts=v[:,0]; p=v[:,1:4]
g=np.loadtxt(gtp); gts=g[:,0]; gp=g[:,1:4]
idx=np.clip(np.searchsorted(gts,ts),0,len(gp)-1); s=p; d=gp[idx]
ms,md=s.mean(0),d.mean(0);S=s-ms;Dd=d-md;C=Dd.T@S/len(s);U,_,Vt=np.linalg.svd(C);R=U@Vt
if np.linalg.det(R)<0:U[:,-1]*=-1;R=U@Vt
ate=np.sqrt((((R@s.T).T+(md-R@ms)-d)**2).sum(1).mean())
dur=ts[-1]-ts[0]
print(f"EGRADE {seq} {grade}: rows={len(v)} dur={dur:.0f}s ATE={ate:.4f}")
tum=np.column_stack([ts,p[:,0],p[:,1],p[:,2],v[:,5],v[:,6],v[:,7],v[:,4]])
np.savetxt(os.path.dirname(vp)+"/vio.tum",tum,fmt="%.9f")
PY