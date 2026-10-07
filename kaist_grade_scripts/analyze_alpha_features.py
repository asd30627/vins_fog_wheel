#!/usr/bin/env python3
"""Analysis (NO experiment re-run): re-derive per-interval optimal rotation-alpha from the SAME existing
.tum files used by the continuous oracle, join to the existing per-keyframe reliability_features
(p1_grade_hard/<seq>/<grade>_rep0/reliability_features.csv, same FOG-aided grid), and ask whether the
INTERIOR (Mixed) intervals carry systematic runtime-observable scene features.

Classes by optimal rotation-alpha a* (FOG weight): VIO-win a<0.2 ; Mixed 0.2<=a<=0.8 ; FOG-win a>0.8.
Outputs: 3-class feature table; urban28 Mixed time-distribution (ascii); Spearman(a* vs feature) within Mixed.
Reuses the exact alpha-search math of probe_continuous_oracle.py."""
import numpy as np, pandas as pd, os, sys
from scipy.stats import spearmanr
EXT="/mnt/sata4t/datasets/kaist_complex_urban/extracted"
P1F="/mnt/sata4t/ivlab3_data/fwvio/results/p1_factors"; P1G="/mnt/sata4t/ivlab3_data/fwvio/results/p1_grade"
P1H="/mnt/sata4t/ivlab3_data/fwvio/results/p1_grade_hard"
GRADES=["kaist_real_005","industrial_fog","precision_mems","general_imu"]
SEQS=["urban26-dongtan","urban27-dongtan","urban28-pankyo","urban29-pankyo"]
ALPHAS=np.round(np.arange(0,1.0001,0.1),3)
def yaw(q): return np.arctan2(2*(q[:,3]*q[:,2]+q[:,0]*q[:,1]),1-2*(q[:,1]**2+q[:,2]**2))
def wrap(a): return (a+np.pi)%(2*np.pi)-np.pi
def fogoff(seq):
    for c in [f"{P1G}/{seq}/fogoff_rep0/vio.tum",f"{P1F}/{seq}/imu_rep0/vio.tum",f"{P1F}/{seq}/imu_rep1/vio.tum"]:
        if os.path.exists(c) and os.path.getsize(c)>100: return c
    return None
def baseline_tum(seq,grade):
    for c in [f"{P1G}/{seq}/{grade}_rep0/vio.tum", f"{P1F}/{seq}/fog_rep0/vio.tum"]:
        if os.path.exists(c) and os.path.getsize(c)>100: return c
    return None
# reliability feature columns of interest (header names)
FCOLS={"feat_mgr":"tracked_feature_count_mgr","outlier_ratio":"outlier_ratio_last",
       "vel_norm":"vel_norm","ba_norm":"ba_norm","bg_norm":"bg_norm",
       "reproj_res":"vg_flow_res_mean","solver_ms":"solver_time_ms_last"}

def per_interval(seq,grade):
    bt=baseline_tum(seq,grade); fo=fogoff(seq)
    if not bt or not fo: return None
    b=np.loadtxt(bt); tb=b[:,0]; yb=np.unwrap(yaw(b[:,4:8]))
    if len(tb)<6: return None
    gt=np.loadtxt(f"{EXT}/{seq}/pose/{seq}/global_pose.tum"); gts=gt[:,0]
    gyaw=np.unwrap(yaw(gt[:,4:8])); gy_at=np.interp(tb,gts,gyaw); dgt=wrap(np.diff(gy_at))
    fov=np.loadtxt(fo); foy=np.unwrap(yaw(fov[:,4:8])); dvis_y=wrap(np.diff(np.interp(tb,fov[:,0],foy)))
    sd=f"{EXT}/{seq}/data/{seq}/sensor_data"; fc=f"{sd}/fog.csv" if grade=="kaist_real_005" else f"{sd}/fog_grade_{grade}.csv"
    f=np.loadtxt(fc,delimiter=","); cum=np.cumsum(f[:,3]); dfog=wrap(np.diff(np.interp(tb,f[:,0]*1e-9,cum)))
    if np.std(dfog)>0 and np.std(dgt)>0: dfog*=np.sign(np.corrcoef(dfog,dgt)[0,1])
    cand=ALPHAS[:,None]*dfog[None,:]+(1-ALPHAS[:,None])*dvis_y[None,:]
    a_star=ALPHAS[np.argmin(np.abs(cand-dgt[None,:]),axis=0)]            # per-interval optimal rotation alpha
    dt=np.diff(tb); dt=np.maximum(dt,1e-6)
    yaw_rate=np.abs(np.diff(yb))/dt                                      # |d yaw_baseline|/dt (rad/s)
    t_end=tb[1:]                                                         # interval-end keyframe timestamp
    # join features by nearest timestamp
    relf=f"{P1H}/{seq}/{grade}_rep0/reliability_features.csv"
    if not (os.path.exists(relf) and os.path.getsize(relf)>200): return None
    df=pd.read_csv(relf);
    if len(df)<6: return None
    fts=df["timestamp"].values
    idx=np.clip(np.searchsorted(fts,t_end),0,len(fts)-1)
    # nearest (searchsorted gives right side; compare with left)
    left=np.clip(idx-1,0,len(fts)-1)
    pick=np.where(np.abs(fts[left]-t_end)<np.abs(fts[idx]-t_end),left,idx)
    out=pd.DataFrame({"seq":seq,"grade":grade,"t":t_end,"alpha":a_star,"yaw_rate":yaw_rate})
    for k,c in FCOLS.items():
        out[k]=df[c].values[pick] if c in df.columns else np.nan
    return out

def main():
    parts=[]
    for s in SEQS:
        for g in GRADES:
            r=per_interval(s,g)
            if r is None or len(r)<6: print(f"# skip {s}/{g}",file=sys.stderr); continue
            parts.append(r)
    D=pd.concat(parts,ignore_index=True)
    D.to_csv("/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts/alpha_feature_intervals.csv",index=False)
    FEATS=["feat_mgr","outlier_ratio","yaw_rate","vel_norm","ba_norm","bg_norm","reproj_res","solver_ms"]
    def cls(a): return np.where(a<0.2,"VIO-win",np.where(a>0.8,"FOG-win","Mixed"))
    D["class"]=cls(D["alpha"].values)
    print(f"# total intervals (all seq/grade, excl RUN_ERROR): {len(D)}")
    n=D["class"].value_counts(); print("# class counts:",dict(n),"\n")
    print("## 3-class feature means")
    print(f"{'feature':14}{'VIO-win':>12}{'Mixed':>12}{'FOG-win':>12}{'spread(Mix-vs-ends)':>22}")
    for f in FEATS:
        mv={c:D.loc[D['class']==c,f].mean() for c in ['VIO-win','Mixed','FOG-win']}
        ends=np.nanmean([mv['VIO-win'],mv['FOG-win']])
        rel=(mv['Mixed']-ends)/(abs(ends)+1e-9)*100
        print(f"{f:14}{mv['VIO-win']:>12.3f}{mv['Mixed']:>12.3f}{mv['FOG-win']:>12.3f}{rel:>20.1f}%")
    # urban28 mixed time distribution
    print("\n## urban28 Mixed-interval time distribution (all grades pooled, 40 bins over run)")
    u=D[D['seq']=='urban28-pankyo'].copy()
    t0,t1=u['t'].min(),u['t'].max(); nb=40; binw=(t1-t0)/nb
    u['bin']=((u['t']-t0)/binw).clip(0,nb-1).astype(int)
    for b in range(nb):
        sub=u[u['bin']==b]; tot=len(sub); mix=(sub['class']=='Mixed').sum()
        frac=mix/tot if tot else 0; bar="#"*int(frac*50)
        ts=t0+b*binw-u['t'].min()
        print(f"  t+{ (t0+b*binw)-t0:6.0f}s mix={mix:4d}/{tot:4d} |{bar}")
    # spearman within Mixed
    print("\n## Spearman(alpha vs feature) within Mixed class")
    M=D[D['class']=='Mixed']
    res=[]
    for f in FEATS:
        x=M['alpha'].values; y=M[f].values; ok=np.isfinite(x)&np.isfinite(y)
        if ok.sum()>10:
            rho,p=spearmanr(x[ok],y[ok]); res.append((f,rho,p,ok.sum()))
    res.sort(key=lambda z:-abs(z[1]))
    print(f"{'feature':14}{'rho':>9}{'p':>12}{'n':>8}")
    for f,rho,p,nn in res: print(f"{f:14}{rho:>9.3f}{p:>12.2e}{nn:>8}")

if __name__=="__main__": main()
