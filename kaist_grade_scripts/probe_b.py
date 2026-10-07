#!/usr/bin/env python3
"""Probe B — GT-only oracle ceiling. Per FOG-off VINS keyframe interval, compare who is closer to GT yaw:
   FOG (graded) vs vision (FOG-off VINS). Data-only (uses GT + injected FOG + one FOG-off VINS pass)."""
import numpy as np, sys, glob, os
EXT="/mnt/sata4t/datasets/kaist_complex_urban/extracted"
P1G="/mnt/sata4t/ivlab3_data/fwvio/results/p1_grade"
P1F="/mnt/sata4t/ivlab3_data/fwvio/results/p1_factors"
GRADES=["kaist_real_005","industrial_fog","precision_mems","general_imu"]
def yaw(qx,qy,qz,qw): return np.arctan2(2*(qw*qz+qx*qy),1-2*(qy*qy+qz*qz))
def wrap(a): return (a+np.pi)%(2*np.pi)-np.pi

def fogoff_tum(seq):
    for c in [f"{P1G}/{seq}/fogoff_rep0/vio.tum", f"{P1F}/{seq}/imu_rep0/vio.tum", f"{P1F}/{seq}/imu_rep1/vio.tum"]:
        if os.path.exists(c) and os.path.getsize(c)>100: return c
    return None

def probe_seq(seq):
    fo=fogoff_tum(seq)
    if not fo: print(f"{seq}: no FOG-off vio.tum yet"); return None
    gt=np.loadtxt(f"{EXT}/{seq}/pose/{seq}/global_pose.tum")
    gt_ts=gt[:,0]; gt_yaw_un=np.unwrap(yaw(gt[:,4],gt[:,5],gt[:,6],gt[:,7]))  # global_pose.tum ts already in seconds
    vo=np.loadtxt(fo); kf_ts=vo[:,0]; kf_yaw=np.unwrap(yaw(vo[:,4],vo[:,5],vo[:,6],vo[:,7]))
    # interval endpoints = consecutive keyframes; need >=2
    if len(kf_ts)<3: print(f"{seq}: too few KF ({len(kf_ts)})"); return None
    # GT yaw interpolated at KF times
    gt_at_kf=np.interp(kf_ts, gt_ts, gt_yaw_un)
    dpsi_vis=wrap(np.diff(kf_yaw)); dpsi_gt=wrap(np.diff(gt_at_kf))
    rows=[]
    sd=f"{EXT}/{seq}/data/{seq}/sensor_data"
    for g in GRADES:
        fcsv = f"{sd}/fog.csv" if g=="kaist_real_005" else f"{sd}/fog_grade_{g}.csv"
        if not os.path.exists(fcsv): rows.append((g,None)); continue
        fog=np.loadtxt(fcsv, delimiter=","); fts=fog[:,0]*1e-9
        cum_z=np.cumsum(fog[:,3])                       # col3 = yaw-axis angle increments -> cumulative
        cum_at_kf=np.interp(kf_ts, fts, cum_z)
        dpsi_fog=wrap(np.diff(cum_at_kf))
        # sign auto-align FOG to GT (handle axis sign convention) via correlation
        s=np.sign(np.corrcoef(dpsi_fog,dpsi_gt)[0,1]); dpsi_fog=dpsi_fog*s
        err_fog=np.abs(dpsi_fog-dpsi_gt); err_vis=np.abs(dpsi_vis-dpsi_gt)
        fog_wins=np.mean(err_fog<err_vis)
        rows.append((g,dict(n=len(dpsi_gt), corr_fog=np.corrcoef(dpsi_fog,dpsi_gt)[0,1],
                            corr_vis=np.corrcoef(dpsi_vis,dpsi_gt)[0,1],
                            err_fog_med=np.median(err_fog), err_vis_med=np.median(err_vis),
                            fog_wins=fog_wins, sign=s)))
    return rows

if __name__=="__main__":
    seqs=sys.argv[1:] or ["urban28-pankyo"]
    print(f"{'seq':16}{'grade':16}{'n':>6}{'corrFOG':>8}{'corrVIS':>8}{'errFOGmed':>11}{'errVISmed':>11}{'FOGwins%':>9}")
    for s in seqs:
        r=probe_seq(s)
        if not r: continue
        for g,d in r:
            if d is None: print(f"{s:16}{g:16}  (missing fog)"); continue
            print(f"{s:16}{g:16}{d['n']:>6}{d['corr_fog']:>8.3f}{d['corr_vis']:>8.3f}{d['err_fog_med']:>11.4f}{d['err_vis_med']:>11.4f}{100*d['fog_wins']:>9.1f}")
