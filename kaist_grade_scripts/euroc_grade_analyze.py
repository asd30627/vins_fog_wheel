#!/usr/bin/env python3
"""Step1 (visual degradation rank) + Step3 (grade-sensitivity vs visual-degradation correlation)
for the EuRoC visual x inertial-grade interaction premise.

Step1 visual proxies per seq:
  - runtime (from runs/<seq>__real/reliability_features_vins.csv): feat_mgr_mean (lower=worse),
    outlier_ratio_mean (higher=worse), coverage8_mean, avg_track_length_mean, entropy8_mean.
  - image (sample of mav0/cam0/data): brightness_mean, contrast_std, dark_frac, sat_frac.
Step3:
  - grade_matrix.tsv -> per seq ATE across grades; grade_sensitivity = ATE_worst - ATE_real (abs)
    and rel = (ATE_worst-ATE_real)/ATE_real. Correlate vs visual proxies (Spearman).
"""
import csv, glob, json, os, sys
import numpy as np

ROOT="/mnt/sata4t/ivlab3_data/fwvio/results/euroc_grade"
RAW={
 'MH_01_easy':'Machine_Hall_Datasets/machine_hall/MH_01_easy','MH_02_easy':'Machine_Hall_Datasets/machine_hall/MH_02_easy',
 'MH_03_medium':'Machine_Hall_Datasets/machine_hall/MH_03_medium','MH_04_difficult':'Machine_Hall_Datasets/machine_hall/MH_04_difficult',
 'MH_05_difficult':'Machine_Hall_Datasets/machine_hall/MH_05_difficult','V1_01_easy':'Vicon_Room_1_Datasets/vicon_room1/V1_01_easy',
 'V1_02_medium':'Vicon_Room_1_Datasets/vicon_room1/V1_02_medium','V1_03_difficult':'Vicon_Room_1_Datasets/vicon_room1/V1_03_difficult',
 'V2_01_easy':'Vicon_Room_2_Datasets/vicon_room2/V2_01_easy','V2_02_medium':'Vicon_Room_2_Datasets/vicon_room2/V2_02_medium',
 'V2_03_difficult':'Vicon_Room_2_Datasets/vicon_room2/V2_03_difficult'}
EUROC_BASE="/mnt/sata4t/datasets/EuRoC_full"
GRADE_ORDER=['real','industrial_fog','precision_mems','general_imu']
LABEL=lambda s: s.split('_')[-1]

def col(rows,name):
    out=[]
    for r in rows:
        try:out.append(float(r[name]))
        except:out.append(np.nan)
    return np.array(out)

def runtime_proxy(seq):
    p=f"{ROOT}/runs/{seq}__real/reliability_features_vins.csv"
    if not os.path.exists(p): return None
    with open(p) as f: rows=list(csv.DictReader(f))
    return dict(
        feat_mgr=np.nanmean(col(rows,'tracked_feature_count_mgr')),
        outlier=np.nanmean(col(rows,'outlier_ratio_last')),
        coverage8=np.nanmean(col(rows,'coverage_8x8')),
        track_len=np.nanmean(col(rows,'avg_track_length')),
        entropy8=np.nanmean(col(rows,'feature_entropy_8x8')))

def image_proxy(seq,nsamp=150):
    import cv2
    d=f"{EUROC_BASE}/{RAW[seq]}/mav0/cam0/data"
    fs=sorted(glob.glob(d+"/*.png"))
    if not fs: return dict(brightness=np.nan,contrast=np.nan,dark_frac=np.nan,sat_frac=np.nan)
    idx=np.linspace(0,len(fs)-1,min(nsamp,len(fs))).astype(int)
    br=[];ct=[];dk=[];st=[]
    for i in idx:
        im=cv2.imread(fs[i],cv2.IMREAD_GRAYSCALE)
        if im is None: continue
        br.append(im.mean());ct.append(im.std())
        dk.append((im<20).mean());st.append((im>235).mean())
    return dict(brightness=float(np.mean(br)),contrast=float(np.mean(ct)),
                dark_frac=float(np.mean(dk)),sat_frac=float(np.mean(st)))

def load_matrix():
    p=f"{ROOT}/grade_matrix.tsv"; M={}
    with open(p) as f:
        next(f)
        for ln in f:
            a=ln.rstrip("\n").split("\t")
            if len(a)<4: continue
            seq,grade,rows,ate=a[0],a[1],a[2],a[3]
            M.setdefault(seq,{})[grade]=dict(rows=int(rows) if rows.isdigit() else 0,
                                             ate=float(ate) if ate not in('NA','') else np.nan)
    return M

def spear(a,b):
    a=np.asarray(a,float);b=np.asarray(b,float)
    m=np.isfinite(a)&np.isfinite(b)
    if m.sum()<4: return float('nan')
    ra=np.argsort(np.argsort(a[m]));rb=np.argsort(np.argsort(b[m]))
    ra=ra-ra.mean();rb=rb-rb.mean()
    d=np.sqrt((ra*ra).sum()*(rb*rb).sum())
    return float((ra*rb).sum()/d) if d>0 else float('nan')

def main():
    M=load_matrix()
    seqs=[s for s in RAW if s in M]
    rec={}
    for s in seqs:
        rp=runtime_proxy(s) or {}
        ip=image_proxy(s)
        gr=M[s]
        ate_real=gr.get('real',{}).get('ate',np.nan)
        ates={g:gr.get(g,{}).get('ate',np.nan) for g in GRADE_ORDER}
        crashed=[g for g in GRADE_ORDER if gr.get(g,{}).get('rows',0)<100]
        finite=[ates[g] for g in GRADE_ORDER if np.isfinite(ates[g])]
        ate_worst=np.nanmax([ates[g] for g in GRADE_ORDER]) if finite else np.nan
        sens_abs=ate_worst-ate_real if np.isfinite(ate_worst) and np.isfinite(ate_real) else np.nan
        sens_rel=sens_abs/ate_real if np.isfinite(sens_abs) and ate_real>0 else np.nan
        rec[s]=dict(label=LABEL(s),**rp,**ip,
                    ate_real=ate_real,ate_industrial=ates['industrial_fog'],
                    ate_precision=ates['precision_mems'],ate_general=ates['general_imu'],
                    ate_worst=ate_worst,sens_abs=sens_abs,sens_rel=sens_rel,
                    crashed=crashed)
    # correlations: grade-sensitivity vs visual proxies
    seqs2=[s for s in seqs if np.isfinite(rec[s]['sens_abs'])]
    def g(k): return [rec[s][k] for s in seqs2]
    sa=g('sens_abs'); sr=g('sens_rel')
    proxies=['feat_mgr','outlier','coverage8','track_len','entropy8','brightness','contrast','dark_frac','sat_frac']
    corr={}
    for px in proxies:
        if all(k in rec[seqs2[0]] for k in [px]):
            corr[px]=dict(vs_sens_abs=spear(g(px),sa),vs_sens_rel=spear(g(px),sr))
    out=dict(n_seq=len(seqs2),records=rec,
             spearman_sensitivity_vs_proxy=corr,
             note="feat_mgr/coverage/track_len/brightness/contrast: HIGHER=better-visual; outlier/dark/sat: HIGHER=worse-visual. Premise: worse visual -> higher sens_abs.")
    print(json.dumps(out,indent=2,default=str))
    with open(f"{ROOT}/grade_analysis.json","w") as f: json.dump(out,f,indent=2,default=str)

if __name__=='__main__': main()
