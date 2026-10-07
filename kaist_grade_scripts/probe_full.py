#!/usr/bin/env python3
"""FOG oracle-ceiling (task 2) + wheel-head probe (task 3). Data-level, GT-referenced, no estimator change.
Per FOG-off VINS keyframe interval:
  yaw:   Dpsi_gt, Dpsi_vis (FOG-off VINS), Dpsi_fog (graded FOG integration)
  trans: |Dp|_gt, |Dp|_vis (FOG-off VINS), |Dp|_wheel (encoder integration)  [distance magnitudes; frame-free]
Outputs:
  FOG oracle ceiling: per grade, per-interval yaw err for always-FOG vs ORACLE(min) + %reduction; accumulated yaw drift.
  Wheel probe: wheel-wins% + median err_wheel vs err_vis (translation distance).
"""
import numpy as np, os, sys
EXT="/mnt/sata4t/datasets/kaist_complex_urban/extracted"
P1F="/mnt/sata4t/ivlab3_data/fwvio/results/p1_factors"
P1G="/mnt/sata4t/ivlab3_data/fwvio/results/p1_grade"
GRADES=["kaist_real_005","industrial_fog","precision_mems","general_imu"]
# KAIST encoder (urban00 calib; same vehicle)
RES=4096; DL=0.623803; DR=0.623095
ML=np.pi*DL/RES; MR=np.pi*DR/RES   # m per tick
def yaw(q): return np.arctan2(2*(q[:,3]*q[:,2]+q[:,0]*q[:,1]),1-2*(q[:,1]**2+q[:,2]**2))
def wrap(a): return (a+np.pi)%(2*np.pi)-np.pi
def fogoff(seq):
    for c in [f"{P1G}/{seq}/fogoff_rep0/vio.tum",f"{P1F}/{seq}/imu_rep0/vio.tum",f"{P1F}/{seq}/imu_rep1/vio.tum"]:
        if os.path.exists(c) and os.path.getsize(c)>100: return c
    return None

def analyze(seq):
    fo=fogoff(seq)
    if not fo: return None
    gt=np.loadtxt(f"{EXT}/{seq}/pose/{seq}/global_pose.tum"); gts=gt[:,0]; gyaw=np.unwrap(yaw(gt[:,4:8])); gx,gy=gt[:,1],gt[:,2]
    vo=np.loadtxt(fo); kt=vo[:,0]; vyaw=np.unwrap(yaw(vo[:,4:8])); vx,vy=vo[:,1],vo[:,2]
    if len(kt)<5: return None
    # GT/vis at keyframe times
    g_at=np.interp(kt,gts,gyaw); gx_at=np.interp(kt,gts,gx); gy_at=np.interp(kt,gts,gy)
    dgt=wrap(np.diff(g_at)); dvis=wrap(np.diff(vyaw))
    # translation increments (distance magnitudes; frame-free)
    dist_gt=np.hypot(np.diff(gx_at),np.diff(gy_at)); dist_vis=np.hypot(np.diff(vx),np.diff(vy))
    # wheel distance per interval (encoder)
    enc=np.loadtxt(f"{EXT}/{seq}/data/{seq}/sensor_data/encoder.csv",delimiter=","); ets=enc[:,0]*1e-9
    l_at=np.interp(kt,ets,enc[:,1]); r_at=np.interp(kt,ets,enc[:,2])
    dist_wheel=0.5*(np.abs(np.diff(l_at))*ML+np.abs(np.diff(r_at))*MR)
    # ---- TASK 3: wheel probe ----
    ew=np.abs(dist_wheel-dist_gt); evt=np.abs(dist_vis-dist_gt)
    wheel=dict(n=len(dist_gt), wheel_wins=np.mean(ew<evt), ew_med=np.median(ew), ev_med=np.median(evt),
               corr_wheel=np.corrcoef(dist_wheel,dist_gt)[0,1], corr_vis=np.corrcoef(dist_vis,dist_gt)[0,1])
    # ---- TASK 2: FOG oracle ceiling, per grade ----
    sd=f"{EXT}/{seq}/data/{seq}/sensor_data"; fog_rows={}
    for g in GRADES:
        fc=f"{sd}/fog.csv" if g=="kaist_real_005" else f"{sd}/fog_grade_{g}.csv"
        if not os.path.exists(fc): fog_rows[g]=None; continue
        f=np.loadtxt(fc,delimiter=","); ft=f[:,0]*1e-9; cum=np.cumsum(f[:,3]); cat=np.interp(kt,ft,cum); dfog=wrap(np.diff(cat))
        s=np.sign(np.corrcoef(dfog,dgt)[0,1]); dfog=dfog*s
        ef=np.abs(dfog-dgt); ev=np.abs(dvis-dgt)
        oracle_err=np.minimum(ef,ev)            # best-of per interval
        # accumulated yaw drift (cumsum of signed errors -> final |drift|)
        drift_fog=np.abs(np.sum(dfog-dgt)); drift_oracle=np.abs(np.sum(np.where(ef<=ev,dfog,dvis)-dgt)); drift_vis=np.abs(np.sum(dvis-dgt))
        fog_rows[g]=dict(fog_wins=np.mean(ef<ev), ef_mean=np.mean(ef), ev_mean=np.mean(ev), oracle_mean=np.mean(oracle_err),
                         redux=100*(np.mean(ef)-np.mean(oracle_err))/max(np.mean(ef),1e-12),
                         drift_fog=drift_fog, drift_oracle=drift_oracle, drift_vis=drift_vis)
    return dict(wheel=wheel, fog=fog_rows)

if __name__=="__main__":
    seqs=sys.argv[1:] or ["urban28-pankyo","urban29-pankyo","urban26-dongtan","urban27-dongtan"]
    print("="*100); print("TASK 2 — FOG oracle-ceiling (per-interval yaw err, rad): always-FOG vs ORACLE(min)")
    print(f"{'seq':16}{'grade':16}{'FOGwins%':>9}{'err_FOG':>10}{'err_VIS':>10}{'err_ORACLE':>11}{'redux%':>8}{'driftFOG':>9}{'driftORC':>9}")
    for s in seqs:
        a=analyze(s)
        if not a: print(f"{s}: no FOG-off"); continue
        for g in GRADES:
            d=a['fog'][g]
            if d is None: continue
            print(f"{s:16}{g:16}{100*d['fog_wins']:>9.1f}{d['ef_mean']:>10.5f}{d['ev_mean']:>10.5f}{d['oracle_mean']:>11.5f}{d['redux']:>8.1f}{d['drift_fog']:>9.3f}{d['drift_oracle']:>9.3f}")
        print()
    print("="*100); print("TASK 3 — wheel-head probe (per-interval translation DISTANCE, m): wheel vs vision")
    print(f"{'seq':16}{'n':>7}{'corrWHEEL':>10}{'corrVIS':>9}{'err_wheel_med':>14}{'err_vis_med':>12}{'WHEELwins%':>11}")
    for s in seqs:
        a=analyze(s)
        if not a: continue
        w=a['wheel']
        print(f"{s:16}{w['n']:>7}{w['corr_wheel']:>10.3f}{w['corr_vis']:>9.3f}{w['ew_med']:>14.4f}{w['ev_med']:>12.4f}{100*w['wheel_wins']:>11.1f}")
