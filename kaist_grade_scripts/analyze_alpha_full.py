#!/usr/bin/env python3
"""Full analysis (NO experiment re-run): re-derive per-interval rotation-alpha AND translation-beta from the
existing .tum files (pure numpy, same math as probe_continuous_oracle.py), join existing per-keyframe
reliability_features + est position, then:
  1. Spearman(alpha, feat) over ALL intervals   2. Spearman(beta, feat) over ALL intervals
  3. 3-class LOSO (by sequence) classification VIO-win/Mixed/FOG-win from vel_norm,yaw_rate,outlier_ratio,reproj_res
  4. urban28 Mixed-interval spatial distribution (map t -> est x,y)."""
import numpy as np, pandas as pd, os, sys
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import confusion_matrix, accuracy_score
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
RES=4096; ML=np.pi*0.623803/RES; MR=np.pi*0.623095/RES
def Rz(a): return np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
FCOLS={"feat_mgr":"tracked_feature_count_mgr","outlier_ratio":"outlier_ratio_last","vel_norm":"vel_norm",
       "ba_norm":"ba_norm","bg_norm":"bg_norm","reproj_res":"vg_flow_res_mean","solver_ms":"solver_time_ms_last"}

def per_interval(seq,grade):
    bt=baseline_tum(seq,grade); fo=fogoff(seq)
    if not bt or not fo: return None
    b=np.loadtxt(bt); tb=b[:,0]; pb=b[:,1:4]; yb=np.unwrap(yaw(b[:,4:8]))
    if len(tb)<6: return None
    gt=np.loadtxt(f"{EXT}/{seq}/pose/{seq}/global_pose.tum"); gts=gt[:,0]
    g_at=np.column_stack([np.interp(tb,gts,gt[:,1]),np.interp(tb,gts,gt[:,2]),np.interp(tb,gts,gt[:,3])])
    gyaw=np.unwrap(yaw(gt[:,4:8])); gy_at=np.interp(tb,gts,gyaw); dgt=wrap(np.diff(gy_at))
    fov=np.loadtxt(fo); foy=np.unwrap(yaw(fov[:,4:8])); dvis_y=wrap(np.diff(np.interp(tb,fov[:,0],foy)))
    sd=f"{EXT}/{seq}/data/{seq}/sensor_data"; fc=f"{sd}/fog.csv" if grade=="kaist_real_005" else f"{sd}/fog_grade_{grade}.csv"
    f=np.loadtxt(fc,delimiter=","); cum=np.cumsum(f[:,3]); dfog=wrap(np.diff(np.interp(tb,f[:,0]*1e-9,cum)))
    if np.std(dfog)>0 and np.std(dgt)>0: dfog*=np.sign(np.corrcoef(dfog,dgt)[0,1])
    # rotation alpha
    cand=ALPHAS[:,None]*dfog[None,:]+(1-ALPHAS[:,None])*dvis_y[None,:]
    a_star=ALPHAS[np.argmin(np.abs(cand-dgt[None,:]),axis=0)]
    # translation beta (wheel vs vision body increment)
    dw=np.diff(pb,axis=0); dbody=np.zeros_like(dw)
    for i in range(len(dw)): xy=Rz(-yb[i])@dw[i,:2]; dbody[i]=[xy[0],xy[1],dw[i,2]]
    enc=np.loadtxt(f"{sd}/encoder.csv",delimiter=","); ets=enc[:,0]*1e-9
    l=np.interp(tb,ets,enc[:,1]); r=np.interp(tb,ets,enc[:,2]); fwd=0.5*(np.abs(np.diff(l))*ML+np.abs(np.diff(r))*MR)
    dist_gt=np.hypot(np.diff(g_at[:,0]),np.diff(g_at[:,1])); n=len(dbody)
    bx=ALPHAS[:,None]*fwd[None,:]+(1-ALPHAS[:,None])*dbody[None,:,0]
    by=(1-ALPHAS[:,None])*dbody[None,:,1]
    b_star=ALPHAS[np.argmin(np.abs(np.hypot(bx,by)-dist_gt[None,:]),axis=0)]
    dt=np.diff(tb); dt=np.maximum(dt,1e-6); yaw_rate=np.abs(np.diff(yb))/dt; t_end=tb[1:]
    relf=f"{P1H}/{seq}/{grade}_rep0/reliability_features.csv"
    if not (os.path.exists(relf) and os.path.getsize(relf)>200): return None
    df=pd.read_csv(relf)
    if len(df)<6: return None
    fts=df["timestamp"].values; idx=np.clip(np.searchsorted(fts,t_end),0,len(fts)-1); left=np.clip(idx-1,0,len(fts)-1)
    pick=np.where(np.abs(fts[left]-t_end)<np.abs(fts[idx]-t_end),left,idx)
    out=pd.DataFrame({"seq":seq,"grade":grade,"t":t_end,"alpha":a_star,"beta":b_star,"yaw_rate":yaw_rate,
                      "est_x":pb[1:,0],"est_y":pb[1:,1]})
    for k,c in FCOLS.items(): out[k]=df[c].values[pick] if c in df.columns else np.nan
    return out

def main():
    parts=[]
    for s in SEQS:
        for g in GRADES:
            r=per_interval(s,g)
            if r is None or len(r)<6: print(f"# skip {s}/{g}",file=sys.stderr); continue
            parts.append(r)
    D=pd.concat(parts,ignore_index=True)
    D.to_csv("/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts/alpha_beta_intervals.csv",index=False)
    FEATS=["feat_mgr","outlier_ratio","yaw_rate","vel_norm","ba_norm","bg_norm","reproj_res","solver_ms"]
    print(f"# total intervals = {len(D)}\n")
    # 1 & 2: Spearman over ALL intervals
    for tgt in ["alpha","beta"]:
        print(f"## Spearman({tgt} vs feature) over ALL {len(D)} intervals")
        res=[]
        for f in FEATS:
            x=D[tgt].values; y=D[f].values; ok=np.isfinite(x)&np.isfinite(y)
            rho,p=spearmanr(x[ok],y[ok]); res.append((f,rho,p))
        res.sort(key=lambda z:-abs(z[1]))
        for f,rho,p in res: print(f"  {f:14}rho={rho:+.3f}  p={p:.2e}")
        print()
    # 3: 3-class LOSO classification
    def cls(a): return np.where(a<0.2,0,np.where(a>0.8,2,1))  # 0 VIO,1 Mixed,2 FOG
    D["y"]=cls(D["alpha"].values)
    CF=["vel_norm","yaw_rate","outlier_ratio","reproj_res"]
    print("## 3-class LOSO (by sequence) — features:",CF)
    names={0:"VIO-win",1:"Mixed",2:"FOG-win"}
    allcm=np.zeros((3,3),int); accs=[]; majaccs=[]
    for test in SEQS:
        tr=D[D.seq!=test]; te=D[D.seq==test]
        Xtr=tr[CF].values; Xte=te[CF].values; ytr=tr.y.values; yte=te.y.values
        m=np.isfinite(Xtr).all(1); mt=np.isfinite(Xte).all(1)
        sc=StandardScaler().fit(Xtr[m])
        clf=LogisticRegression(max_iter=1000,class_weight="balanced",multi_class="multinomial").fit(sc.transform(Xtr[m]),ytr[m])
        pred=clf.predict(sc.transform(Xte[mt])); acc=accuracy_score(yte[mt],pred)
        maj=np.bincount(ytr[m],minlength=3).argmax(); majacc=(yte[mt]==maj).mean()
        cm=confusion_matrix(yte[mt],pred,labels=[0,1,2]); allcm+=cm; accs.append(acc); majaccs.append(majacc)
        print(f"  fold test={test:16} acc={acc:.3f}  majority-baseline={majacc:.3f}")
    print(f"  MEAN acc={np.mean(accs):.3f}  MEAN majority-baseline={np.mean(majaccs):.3f}")
    print("  pooled confusion matrix (rows=true, cols=pred) [VIO,Mixed,FOG]:")
    print("            pred_VIO  pred_Mix  pred_FOG")
    for i in range(3):
        row=allcm[i]; print(f"   true_{names[i]:8}{row[0]:9d}{row[1]:10d}{row[2]:10d}  (recall={row[i]/max(row.sum(),1):.2f})")
    # 4: urban28 Mixed spatial distribution
    print("\n## urban28 Mixed-interval SPATIAL distribution (est x,y; all grades pooled)")
    u=D[D.seq=="urban28-pankyo"].copy(); u["mix"]=(u.y==1)
    nb=24; xs,ys=u.est_x.values,u.est_y.values
    x0,x1,y0,y1=xs.min(),xs.max(),ys.min(),ys.max()
    gx=((xs-x0)/(x1-x0+1e-9)*(nb-1)).astype(int); gy=((ys-y0)/(y1-y0+1e-9)*(nb-1)).astype(int)
    tot=np.zeros((nb,nb)); mix=np.zeros((nb,nb))
    for i in range(len(u)): tot[gy[i],gx[i]]+=1; mix[gy[i],gx[i]]+=u.mix.values[i]
    frac=np.where(tot>0,mix/tot,np.nan)
    print(f"  trajectory bbox: x[{x0:.0f},{x1:.0f}] y[{y0:.0f},{y1:.0f}] m; cell={ (x1-x0)/nb:.0f}x{(y1-y0)/nb:.0f} m")
    print(f"  overall urban28 Mixed fraction = {u.mix.mean():.3f}")
    print("  per-cell Mixed fraction ( .=<10% :=10-20% +=20-30% *=30-40% #=>40%  blank=no traj ):")
    def ch(f):
        if np.isnan(f): return ' '
        return '.' if f<.1 else ':' if f<.2 else '+' if f<.3 else '*' if f<.4 else '#'
    for r in range(nb-1,-1,-1):
        print("   "+"".join(ch(frac[r,c]) for c in range(nb)))
    # quantify spatial concentration: std of per-cell mixed fraction vs binomial expectation
    occ=tot>30; fr=frac[occ]
    print(f"  occupied cells(>30 pts)={occ.sum()}  Mixed-frac across cells: mean={np.nanmean(fr):.3f} std={np.nanstd(fr):.3f} min={np.nanmin(fr):.3f} max={np.nanmax(fr):.3f}")

if __name__=="__main__": main()
