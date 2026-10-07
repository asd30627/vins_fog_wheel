#!/usr/bin/env python3
"""CONTINUOUS rotation-alpha oracle for FOG-aided VIO, WHEEL OFF (translation = VIO, no beta).
Baseline = p1_grade FOG-aided VIO (vins.log: FOG=0 WHEEL=0 P1-factors; IMU = FOG-gyro+xsens-accel) -> the
requested config already exists, no VINS re-run. Per interval, rotation alpha in {0..1}: dpsi(a)=a*dFOG+(1-a)*dVIO_yaw,
a*=argmin|dpsi-dGT_yaw|. Recompose with a-blended yaw + VIO body translation (NO wheel). Binary = endpoints {0,1}.
Reports per (seq,grade): raw vio.tum ATE, reintegrated base ATE, binary, continuous, improve%/gap.
Also dumps per-interval a* for feature analysis. ⚠ GT-selected => OPTIMISTIC UPPER BOUND (but KAIST GT is
RTK-dominated and does NOT contain camera/xsens -> clean for this problem)."""
import numpy as np, os, sys, pandas as pd
EXT="/mnt/sata4t/datasets/kaist_complex_urban/extracted"
P1F="/mnt/sata4t/ivlab3_data/fwvio/results/p1_factors"; P1G="/mnt/sata4t/ivlab3_data/fwvio/results/p1_grade"
P1H="/mnt/sata4t/ivlab3_data/fwvio/results/p1_grade_hard"
GRADES=["kaist_real_005","industrial_fog","precision_mems","general_imu"]
SEQS=["urban26-dongtan","urban27-dongtan","urban28-pankyo","urban29-pankyo"]
ALPHAS=np.round(np.arange(0,1.0001,0.1),3)
def yaw(q): return np.arctan2(2*(q[:,3]*q[:,2]+q[:,0]*q[:,1]),1-2*(q[:,1]**2+q[:,2]**2))
def wrap(a): return (a+np.pi)%(2*np.pi)-np.pi
def Rz(a): return np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
def ate(P,G):
    mp,mg=P.mean(0),G.mean(0); Pc,Gc=P-mp,G-mg; C=Gc.T@Pc/len(P)
    U,_,Vt=np.linalg.svd(C); R=U@Vt
    if np.linalg.det(R)<0: U[:,-1]*=-1; R=U@Vt
    Pal=(R@P.T).T+(mg-R@mp); return np.sqrt(((Pal-G)**2).sum(1).mean())
def ate3(tum,g_at):  # raw vio.tum (full 3D) ATE vs GT-at-keyframes
    return ate(tum[:,1:4],g_at)
def reintegrate(p0,yaws,dbody):
    P=np.zeros((len(yaws),3)); P[0]=p0
    for i in range(len(yaws)-1):
        d=dbody[i]; xy=Rz(yaws[i])@d[:2]; P[i+1]=P[i]+np.array([xy[0],xy[1],d[2]])
    return P
def fogoff(seq):
    for c in [f"{P1G}/{seq}/fogoff_rep0/vio.tum",f"{P1F}/{seq}/imu_rep0/vio.tum",f"{P1F}/{seq}/imu_rep1/vio.tum"]:
        if os.path.exists(c) and os.path.getsize(c)>100: return c
    return None
def baseline_tum(seq,grade):
    for c in [f"{P1G}/{seq}/{grade}_rep0/vio.tum", f"{P1F}/{seq}/fog_rep0/vio.tum"]:
        if os.path.exists(c) and os.path.getsize(c)>100: return c
    return None
FCOLS={"feat_mgr":"tracked_feature_count_mgr","outlier_ratio":"outlier_ratio_last","vel_norm":"vel_norm",
       "ba_norm":"ba_norm","bg_norm":"bg_norm","reproj_res":"vg_flow_res_mean","solver_ms":"solver_time_ms_last"}

def run(seq,grade,collect):
    bt=baseline_tum(seq,grade); fo=fogoff(seq)
    if not bt or not fo: return None
    b=np.loadtxt(bt); tb=b[:,0]; pb=b[:,1:4]; yb=np.unwrap(yaw(b[:,4:8]))
    if len(tb)<6: return None
    gt=np.loadtxt(f"{EXT}/{seq}/pose/{seq}/global_pose.tum"); gts=gt[:,0]
    g_at=np.column_stack([np.interp(tb,gts,gt[:,1]),np.interp(tb,gts,gt[:,2]),np.interp(tb,gts,gt[:,3])])
    gyaw=np.unwrap(yaw(gt[:,4:8])); gy_at=np.interp(tb,gts,gyaw); dgt=wrap(np.diff(gy_at))
    dw=np.diff(pb,axis=0); dbody=np.zeros_like(dw)
    for i in range(len(dw)): xy=Rz(-yb[i])@dw[i,:2]; dbody[i]=[xy[0],xy[1],dw[i,2]]
    fov=np.loadtxt(fo); foy=np.unwrap(yaw(fov[:,4:8])); dvis_y=wrap(np.diff(np.interp(tb,fov[:,0],foy)))
    sd=f"{EXT}/{seq}/data/{seq}/sensor_data"; fc=f"{sd}/fog.csv" if grade=="kaist_real_005" else f"{sd}/fog_grade_{grade}.csv"
    f=np.loadtxt(fc,delimiter=","); cum=np.cumsum(f[:,3]); dfog=wrap(np.diff(np.interp(tb,f[:,0]*1e-9,cum)))
    if np.std(dfog)>0 and np.std(dgt)>0: dfog*=np.sign(np.corrcoef(dfog,dgt)[0,1])
    n=len(dbody)
    cand=ALPHAS[:,None]*dfog[None,:]+(1-ALPHAS[:,None])*dvis_y[None,:]
    err=np.abs(cand-dgt[None,:]); ai=np.argmin(err,axis=0); a_star=ALPHAS[ai]
    abi=np.argmin(np.vstack([err[0],err[-1]]),axis=0); a_bin=abi.astype(float)
    dpsi_cont=cand[ai,np.arange(n)]; dpsi_bin=np.where(a_bin==1,dfog,dvis_y)
    y_cont=np.concatenate([[yb[0]],yb[0]+np.cumsum(dpsi_cont)]); y_bin=np.concatenate([[yb[0]],yb[0]+np.cumsum(dpsi_bin)])
    # recompose with VIO translation (NO wheel)
    A_base=ate(reintegrate(pb[0],yb,dbody),g_at)
    A_bin =ate(reintegrate(pb[0],y_bin,dbody),g_at)
    A_cont=ate(reintegrate(pb[0],y_cont,dbody),g_at)
    A_raw =ate3(b,g_at)
    red=lambda a:100*(A_base-a)/max(A_base,1e-9)
    # collect per-interval features for step 3
    if collect is not None:
        relf=f"{P1H}/{seq}/{grade}_rep0/reliability_features.csv"
        if os.path.exists(relf) and os.path.getsize(relf)>200:
            df=pd.read_csv(relf); fts=df["timestamp"].values; t_end=tb[1:]
            idx=np.clip(np.searchsorted(fts,t_end),0,len(fts)-1); left=np.clip(idx-1,0,len(fts)-1)
            pick=np.where(np.abs(fts[left]-t_end)<np.abs(fts[idx]-t_end),left,idx)
            dt=np.diff(tb); dt=np.maximum(dt,1e-6)
            out=pd.DataFrame({"seq":seq,"grade":grade,"alpha":a_star,"yaw_rate":np.abs(np.diff(yb))/dt})
            for k,c in FCOLS.items(): out[k]=df[c].values[pick] if c in df.columns else np.nan
            collect.append(out)
    return dict(raw=A_raw,base=A_base,binary=A_bin,cont=A_cont,bin_r=red(A_bin),cont_r=red(A_cont),a_star=a_star)

if __name__=="__main__":
    print("# FOG-aided VIO, WHEEL OFF — continuous rotation-alpha oracle. GT-selected upper bound (clean GT).\n")
    print("## Step1+2 per (seq,grade)")
    print(f"{'seq':16}{'grade':16}{'ATE_raw':>9}{'ATE_base':>9}{'ATE_bin':>9}{'ATE_cont':>9}{'bin%':>7}{'cont%':>8}{'gap%':>7}")
    rows=[]; allA=[]; coll=[]
    for s in SEQS:
        for g in GRADES:
            r=run(s,g,coll)
            if r is None: print(f"{s:16}{g:16}  (skip RUN_ERROR/missing)"); continue
            rows.append((s,g,r)); allA.extend(r['a_star'])
            gap=r['cont_r']-r['bin_r']
            print(f"{s:16}{g:16}{r['raw']:>9.2f}{r['base']:>9.2f}{r['binary']:>9.2f}{r['cont']:>9.2f}{r['bin_r']:>7.1f}{r['cont_r']:>8.1f}{gap:>7.1f}")
        print()
    br=[r['bin_r'] for _,_,r in rows]; cr=[r['cont_r'] for _,_,r in rows]; gp=[r['cont_r']-r['bin_r'] for _,_,r in rows]
    print(f"binary improve% : median={np.median(br):.1f} min={min(br):.1f} max={max(br):.1f}")
    print(f"continuous imp% : median={np.median(cr):.1f} min={min(cr):.1f} max={max(cr):.1f}")
    print(f"gap (cont-bin)% : median={np.median(gp):.1f} min={min(gp):.1f} max={max(gp):.1f}")
    A=np.array(allA); print(f"\nalpha: endpoint{{0,1}}={np.mean((A==0)|(A==1))*100:.1f}%  interior={np.mean((A>0)&(A<1))*100:.1f}%  n={len(A)}")
    if coll:
        D=pd.concat(coll,ignore_index=True)
        D.to_csv("/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts/alpha_nowheel_intervals.csv",index=False)
        print(f"# dumped {len(D)} interval rows -> alpha_nowheel_intervals.csv")
