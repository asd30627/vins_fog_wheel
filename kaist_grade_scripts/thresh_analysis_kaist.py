#!/usr/bin/env python3
"""Investigate whether Bas.norm()>2.5 failure threshold is protective or too conservative — KAIST hard.
Per (seq,grade): trigger time, ba_norm at trigger, max ba_norm, 30s-before trend (gradual vs sudden),
ATE up to trigger (Umeyama vio.tum vs GT). Uses reliability_features.csv (ba_norm per keyframe)."""
import glob, os
import numpy as np, pandas as pd

P1H = "/mnt/sata4t/ivlab3_data/fwvio/results/p1_grade_hard"
EXT = "/mnt/sata4t/datasets/kaist_complex_urban/extracted"
THR = 2.5
SEQS = ["urban18-highway","urban19-highway","urban22-highway","urban24-highway","urban30-gangnam","urban38-pankyo"]
GRADES = ["kaist_real_005","industrial_fog","precision_mems","general_imu"]

def um_ate(s, d):
    if len(s) < 3: return float('nan')
    ms, md = s.mean(0), d.mean(0); S = s-ms; D = d-md; C = D.T@S/len(s)
    U,_,Vt = np.linalg.svd(C); R = U@Vt
    if np.linalg.det(R) < 0: U[:,-1]*=-1; R = U@Vt
    return float(np.sqrt((((R@s.T).T+(md-R@ms)-d)**2).sum(1)).mean())

def ate_to(seq, vt_path, t_end_ts):
    if not os.path.exists(vt_path) or os.path.getsize(vt_path) < 50: return float('nan'), 0
    v = np.loadtxt(vt_path)
    if v.ndim < 2: return float('nan'), 0
    m = v[:,0] <= t_end_ts
    v = v[m]
    if len(v) < 3: return float('nan'), len(v)
    gt = np.loadtxt(f"{EXT}/{seq}/pose/{seq}/global_pose.tum")
    idx = np.clip(np.searchsorted(gt[:,0], v[:,0]), 0, len(gt)-1)
    return um_ate(v[:,1:4], gt[idx,1:4]), len(v)

def nearest(ts, ba, t):
    i = int(np.argmin(np.abs(ts - t)))
    return ba[i]

print(f"{'seq':16}{'grade':16}{'nkf':>5}{'dur_s':>7}{'trig_s':>8}{'ba@trig':>9}{'ba_max':>8}"
      f"{'ba@-30s':>9}{'ba@-10s':>9}{'ba@-2s':>8}{'trend':>9}{'ATE@trig':>10}{'nvio':>6}")
for seq in SEQS:
    for g in GRADES:
        csv = f"{P1H}/{seq}/{g}_rep0/reliability_features.csv"
        if not os.path.exists(csv): continue
        df = pd.read_csv(csv)
        if 'ba_norm' not in df or len(df) < 2:
            print(f"{seq:16}{g:16}{len(df):>5}  (no usable ba_norm)"); continue
        ts = df['timestamp'].astype(float).values; ba = df['ba_norm'].astype(float).values
        t0 = ts[0]; rel = ts - t0; dur = rel[-1]
        trig_idx = np.where(ba > THR)[0]
        ba_max = float(np.nanmax(ba))
        if len(trig_idx):
            ti = trig_idx[0]; trig_t = rel[ti]; ba_trig = ba[ti]
            ba_30 = nearest(rel, ba, trig_t-30); ba_10 = nearest(rel, ba, trig_t-10); ba_2 = nearest(rel, ba, trig_t-2)
            # gradual vs sudden: time from last ba<1.0 to trigger
            below = np.where((ba < 1.0) & (rel < trig_t))[0]
            ramp = trig_t - rel[below[-1]] if len(below) else trig_t
            trend = "SUDDEN" if ramp < 3.0 else ("gradual" if ramp > 10.0 else "mid")
            ate, nvio = ate_to(seq, f"{P1H}/{seq}/{g}_rep0/vio.tum", ts[ti])
            print(f"{seq:16}{g:16}{len(df):>5}{dur:>7.1f}{trig_t:>8.1f}{ba_trig:>9.2f}{ba_max:>8.2f}"
                  f"{ba_30:>9.2f}{ba_10:>9.2f}{ba_2:>8.2f}{trend:>9}{(f'{ate:.1f}' if ate==ate else 'NA'):>10}{nvio:>6}")
        else:
            # no trigger (e.g. urban38 real) — closest approach to 2.5
            print(f"{seq:16}{g:16}{len(df):>5}{dur:>7.1f}{'none':>8}{'-':>9}{ba_max:>8.2f}"
                  f"{'-':>9}{'-':>9}{'-':>8}{'NO-TRIG':>9}{'-':>10}{'-':>6}")
    print()
