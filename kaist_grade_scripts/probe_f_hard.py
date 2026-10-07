#!/usr/bin/env python3
"""Probe F (HARD seqs) — grade vs FAILURE/SURVIVAL on scale-hard KAIST sequences.
Signals per (seq,grade): mid-run crash, completion ratio (vio_rows/stereo_frames),
final ATE (drift), scale-collapse-segment% (windowed VINS/GT cumulative-dist ratio outside [0.85,1.15]).
Interpretation handed to user — grade TREND only; KAIST GT is iSAM(FOG+wheel+RTK)-fused (circular),
so absolute ATE = optimistic. Crash/completion/scale-collapse are estimator-internal (less GT-circular)."""
import numpy as np, os, glob, sys
EXT="/mnt/sata4t/datasets/kaist_complex_urban/extracted"
P1H="/mnt/sata4t/ivlab3_data/fwvio/results/p1_grade_hard"
HARD=["urban18-highway","urban19-highway","urban20-highway","urban21-highway",
      "urban22-highway","urban24-highway","urban30-gangnam","urban38-pankyo"]
GRADES=["kaist_real_005","industrial_fog","precision_mems","general_imu"]

def stereo_frames(seq):
    f=f"{EXT}/{seq}/data/{seq}/sensor_data/stereo_stamp.csv"
    return sum(1 for _ in open(f)) if os.path.exists(f) else 0

def gt_load(seq):
    g=np.loadtxt(f"{EXT}/{seq}/pose/{seq}/global_pose.tum"); return g[:,0],g[:,1:4]

def scale_collapse_pct(seq, vt, win_s=5.0):
    if not os.path.exists(vt) or os.path.getsize(vt)<200: return (None,0)
    v=np.loadtxt(vt)
    if v.ndim<2 or len(v)<10: return (None,0)
    ts=v[:,0]; p=v[:,1:4]
    gts,gp=gt_load(seq)
    g_at=np.column_stack([np.interp(ts,gts,gp[:,i]) for i in range(3)])
    bad=tot=0
    edges=np.arange(ts[0],ts[-1],win_s)
    for a,b in zip(edges[:-1],edges[1:]):
        m=(ts>=a)&(ts<b)
        if m.sum()<3: continue
        vd=np.sum(np.linalg.norm(np.diff(p[m],axis=0),axis=1))
        gd=np.sum(np.linalg.norm(np.diff(g_at[m],axis=0),axis=1))
        if gd<1.0: continue
        r=vd/gd; tot+=1
        if r<0.85 or r>1.15: bad+=1
    return (100*bad/tot if tot else None, tot)

def ate_rmse(d):
    f=f"{d}/metrics/ape_vio.txt"
    if not os.path.exists(f): return None
    for ln in open(f,errors='ignore'):
        s=ln.strip()
        if s.startswith("rmse"):
            try: return float(s.split()[-1])
            except: return None
    return None

def died_midrun(d):
    for f in [f"{d}/runner.log"]:
        if os.path.exists(f):
            t=open(f,errors='ignore').read()
            if "died unexpectedly" in t or "vio.csv not found or empty" in t: return True
    return False

if __name__=="__main__":
    seqs = sys.argv[1:] if len(sys.argv)>1 else HARD
    print(f"{'seq':16}{'grade':16}{'crash':>6}{'rows':>7}{'frames':>7}{'compl%':>8}{'ATE_m':>9}{'scaleColl%':>11}{'nwin':>6}")
    for s in seqs:
        nf=stereo_frames(s)
        for g in GRADES:
            d=f"{P1H}/{s}/{g}_rep0"
            if not os.path.isdir(d): print(f"{s:16}{g:16}{'?':>6}{'no_dir':>7}"); continue
            vt=f"{d}/vio.tum"
            nrow=sum(1 for _ in open(vt)) if os.path.exists(vt) else 0
            crash = died_midrun(d) or nrow<100
            compl = 100.0*nrow/nf if nf else 0
            ate=ate_rmse(d)
            sc=scale_collapse_pct(s,vt)
            print(f"{s:16}{g:16}{('YES' if crash else 'no'):>6}{nrow:>7}{nf:>7}{compl:>8.1f}"
                  f"{(f'{ate:.2f}' if ate is not None else 'NA'):>9}"
                  f"{(f'{sc[0]:.1f}' if sc[0] is not None else 'NA'):>11}{sc[1]:>6}")
        print()
