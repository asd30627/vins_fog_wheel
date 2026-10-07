#!/usr/bin/env python3
"""Probe F — grade vs FAILURE events (existing Curve-1 runs + logs; no new machine runs).
Per seq x grade: crash? completed? vio_rows; scale-collapse-segment% (per-window VINS/GT speed ratio outside [0.85,1.15]).
Interpretation handed to user (grade trend only; absolute numbers not claimed)."""
import numpy as np, os, glob, sys
EXT="/mnt/sata4t/datasets/kaist_complex_urban/extracted"
P1G="/mnt/sata4t/ivlab3_data/fwvio/results/p1_grade"
SEQS=["urban28-pankyo","urban29-pankyo","urban26-dongtan","urban27-dongtan"]
GRADES=["kaist_real_005","industrial_fog","precision_mems","general_imu"]
def yaw(q): return np.arctan2(2*(q[:,3]*q[:,2]+q[:,0]*q[:,1]),1-2*(q[:,1]**2+q[:,2]**2))

def rundir(seq,grade):
    for d in [f"{P1G}/{seq}/{grade}_rep0", f"{P1G}/{seq}/{grade}_rep0_retry"]:
        if os.path.isdir(d): return d
    return None

def scale_collapse_pct(seq, vt, win_s=5.0):
    if not os.path.exists(vt) or os.path.getsize(vt)<200: return None
    v=np.loadtxt(vt)
    if v.ndim<2 or len(v)<10: return None
    ts=v[:,0]; p=v[:,1:4]
    gt=np.loadtxt(f"{EXT}/{seq}/pose/{seq}/global_pose.tum"); gts=gt[:,0]; gp=gt[:,1:4]
    g_at=np.column_stack([np.interp(ts,gts,gp[:,0]),np.interp(ts,gts,gp[:,1]),np.interp(ts,gts,gp[:,2])])
    # windowed cumulative-distance ratio
    t0=ts[0]; bad=0; tot=0
    edges=np.arange(ts[0],ts[-1],win_s)
    for a,b in zip(edges[:-1],edges[1:]):
        m=(ts>=a)&(ts<b)
        if m.sum()<3: continue
        vd=np.sum(np.linalg.norm(np.diff(p[m],axis=0),axis=1)); gd=np.sum(np.linalg.norm(np.diff(g_at[m],axis=0),axis=1))
        if gd<1.0: continue
        r=vd/gd; tot+=1
        if r<0.85 or r>1.15: bad+=1
    return (100*bad/tot if tot else None, tot)

def crashed(d):
    for f in glob.glob(f"{d}/*.log")+[f"{d}/vins.log"]:
        if os.path.exists(f):
            try:
                t=open(f,errors='ignore').read()
                if "no matching timestamps" in t: return True
            except: pass
    return False

if __name__=="__main__":
    print(f"{'seq':16}{'grade':16}{'crash':>6}{'completed':>10}{'vio_rows':>9}{'scale_collapse%':>16}{'n_win':>7}")
    for s in SEQS:
        for g in GRADES:
            d=rundir(s,g)
            if not d: print(f"{s:16}{g:16}{'?':>6}{'no_dir':>10}"); continue
            vt=f"{d}/vio.tum"
            nrow=sum(1 for _ in open(vt)) if os.path.exists(vt) else 0
            cr=(nrow<100)
            comp = (nrow>50 and not cr)
            sc=scale_collapse_pct(s,vt)
            scpct = f"{sc[0]:.1f}" if sc and sc[0] is not None else "NA"
            nwin = sc[1] if sc else 0
            print(f"{s:16}{g:16}{('YES' if cr else 'no'):>6}{('yes' if comp else 'NO'):>10}{nrow:>9}{scpct:>16}{nwin:>7}")
        print()
