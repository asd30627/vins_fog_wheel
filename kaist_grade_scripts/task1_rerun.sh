#!/usr/bin/env bash
# Re-run the "too-conservative" seqs with failureDetection DISABLED (return false rebuilt binary).
WBIN=/home/ivlab3/fwvio_estimator_ws_wheel/install/vins/lib/vins/vins_node
SP=/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts
GF=/home/ivlab3/miniconda3/envs/gf/bin/python
P1H=/mnt/sata4t/ivlab3_data/fwvio/results/p1_grade_hard
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
ROW=$SP/task1_rerun_rows.tsv
printf "source\tseq_town\tgrade_route\tvio_rows\tcompletion%%\tATE_m\tearly\tlate\tlate_over_early\tverdict\n" > "$ROW"
kanalyze(){ # seq grade dst -> echo metrics
  local seq=$1 grade=$2 D=$3
  $GF - "$seq" "$grade" "$D" "$ROW" <<'PY'
import sys,os,numpy as np
seq,grade,D,ROW=sys.argv[1:5]
EXT="/mnt/sata4t/datasets/kaist_complex_urban/extracted"
vt=f"{D}/vio.tum"
def stereo(seq):
    f=f"{EXT}/{seq}/data/{seq}/sensor_data/stereo_stamp.csv"; return sum(1 for _ in open(f)) if os.path.exists(f) else 0
nv=0; compl=0; ate=float('nan'); early=float('nan'); late=float('nan')
if os.path.exists(vt) and os.path.getsize(vt)>100:
    v=np.loadtxt(vt); nv=len(v); ts=v[:,0]; p=v[:,1:4]
    nf=stereo(seq); compl=100*nv/nf if nf else 0
    gt=np.loadtxt(f"{EXT}/{seq}/pose/{seq}/global_pose.tum"); gts=gt[:,0]; gp=gt[:,1:4]
    vsp=np.r_[0,np.linalg.norm(np.diff(p,axis=0),axis=1)/np.maximum(np.diff(ts),1e-3)]
    gsp=np.r_[0,np.linalg.norm(np.diff(gp,axis=0),axis=1)/np.maximum(np.diff(gts),1e-3)]
    t0=ts[0]; rr=[]
    for i in range(len(ts)):
        gi=min(np.searchsorted(gts,ts[i]),len(gsp)-1)
        if gsp[gi]>0.3: rr.append((ts[i]-t0, vsp[i]/gsp[gi]))
    e=[r for t,r in rr if t<11]; l=[r for t,r in rr if t>20]
    early=np.median(e) if e else float('nan'); late=np.median(l) if l else float('nan')
    idx=np.clip(np.searchsorted(gts,ts),0,len(gp)-1); s=p; d=gp[idx]
    ms,md=s.mean(0),d.mean(0); S=s-ms; Dd=d-md; C=Dd.T@S/len(s); U,_,Vt=np.linalg.svd(C); R=U@Vt
    if np.linalg.det(R)<0: U[:,-1]*=-1; R=U@Vt
    ate=np.sqrt((((R@s.T).T+(md-R@ms)-d)**2).sum(1)).mean()
loe=late/early if (early==early and early>0 and late==late) else float('nan')
verd="救活(saved)" if (loe==loe and loe<1.5) else ("本來就該死(should-die)" if (loe==loe and loe>5) else "邊際")
open(ROW,'a').write(f"KAIST\t{seq}\t{grade}\t{nv}\t{compl:.1f}\t{ate:.1f}\t{early:.3f}\t{late:.3f}\t{loe:.2f}\t{verd}\n")
print(f"  KAIST {seq}/{grade}: rows={nv} compl={compl:.1f}% ATE={ate:.1f} early={early:.3f} late={late:.3f} L/E={loe:.2f} :: {verd}")
PY
}
echo "===== KAIST (failureDetection disabled) $(date +%H:%M:%S) ====="
export VINS_BIN_OVERRIDE="$WBIN"
for t in "urban30-gangnam kaist_real_005" "urban38-pankyo industrial_fog" "urban38-pankyo precision_mems" "urban38-pankyo general_imu"; do
  set -- $t; seq=$1 grade=$2
  echo "[t1] $seq / $grade  $(date +%H:%M:%S)"
  bash "$SP/run_hard_one.sh" "$seq" "$grade" nofd > "$SP/t1_${seq}_${grade}.log" 2>&1
  kanalyze "$seq" "$grade" "$P1H/$seq/${grade}_repnofd"
done
unset VINS_BIN_OVERRIDE

echo "===== CARLA (failureDetection disabled; _wheel binary is default) $(date +%H:%M:%S) ====="
cd /home/ivlab3/fwvio_ws
CFG640=/home/ivlab3/fwvio_estimator_ws_wheel/src/VINS-Fusion-ROS2-jazzy/config/carla/carla_stereo_imu_640_R3_b05_wheel.yaml
export WHEEL_FACTOR_ENABLE=1 WHEEL_MODE=se2 CARLA_WHEEL_SIGMA=0.001
PY=/home/ivlab3/miniconda3/envs/carla/bin/python
for t in "Town01 rA" "Town07 rA"; do
  set -- $t; town=$1 route=$2; D=/mnt/sata4t/datasets/carla_fwvio/${town}__clean__run${route}
  $PY scripts/gen_carla_wheel.py "$D" >/dev/null 2>&1
  $PY scripts/gen_carla_grade_imu.py --seq "$D" --grade ideal_imu >/dev/null 2>&1
  $PY scripts/make_player_imu_yref.py --in "$D/imu_grade_ideal_imu.csv" --out "$D/imu_grade_ideal_imu_yref.csv" --skip-imu-head 0 >/dev/null 2>&1
  export RC_CONFIG="$CFG640" REL_WHEEL_PRELOAD="$D/carla_wheel.csv"
  tag="t1_${town}_${route}_nofd"; RES=/mnt/sata4t/ivlab3_data/fwvio/results/carla_vins/$tag
  echo "[t1] CARLA $town/$route  $(date +%H:%M:%S)"
  bash scripts/run_carla_grade_vins.sh "$D" ideal_imu "$tag" 0.5 0 0 > "$SP/t1_carla_${town}_${route}.log" 2>&1
  a=$($PY scripts/town_analyze.py "$D" "$RES" 300 2>/dev/null)
  io=$(echo "$a"|grep -oE 'init_ok=[0-9]+'|cut -d= -f2); cp=$(echo "$a"|grep -oE 'completion=[0-9.]+'|cut -d= -f2)
  at=$(echo "$a"|grep -oE 'ATE=[0-9.-]+'|cut -d= -f2); ea=$(echo "$a"|grep -oE 'early=[0-9.]+'|cut -d= -f2)
  la=$(echo "$a"|grep -oE 'late=[0-9.na]+'|cut -d= -f2); vr=$(wc -l < "$RES/vio.csv" 2>/dev/null || echo 0)
  loe=$($GF -c "e=$ea; l='$la';
print('%.2f'%(float(l)/e) if (e>0 and l not in ('nan','')) else 'nan')" 2>/dev/null)
  verd=$($GF -c "x='$loe'; print('救活(saved)' if (x not in ('nan','') and float(x)<1.5) else ('本來就該死(should-die)' if (x not in ('nan','') and float(x)>5) else '邊際'))" 2>/dev/null)
  printf "CARLA\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$town" "gturn@0/$route" "$vr" "$cp" "$at" "$ea" "$la" "$loe" "$verd" >> "$ROW"
  echo "  CARLA $town/$route: rows=$vr compl=$cp% ATE=$at early=$ea late=$la L/E=$loe :: $verd"
done
echo "===== TASK1 DONE $(date +%H:%M:%S) ====="
