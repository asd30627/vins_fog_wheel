#!/usr/bin/env python3
"""Position-ATE oracle ceiling (the go/no-go). Data-level reconstruction on the Curve-1 (FOG-aided)
baseline trajectory grid; no estimator change. For each (seq,grade):
  baseline   = Curve-1 FOG-aided vio.tum (its yaw + its body translation increments) -> ATE_base (== evo Curve1)
  FOG-oracle = ORACLE yaw (per-interval best of FOG vs FOG-off-vision vs GT) + baseline translation -> ATE
  wheelOracle= baseline yaw + ORACLE translation (per-interval best of wheel vs baseline-vision vs GT) -> ATE
ATE = SE(3)-Umeyama-aligned RMS position error vs GT (no scale; matches the Curve-1 evo APE).
NOTE: oracle SELECTION uses GT which on KAIST fuses wheel+FOG (circular) -> oracle is OPTIMISTIC = a true ceiling."""
import numpy as np, os, sys
EXT="/mnt/sata4t/datasets/kaist_complex_urban/extracted"
P1F="/mnt/sata4t/ivlab3_data/fwvio/results/p1_factors"; P1G="/mnt/sata4t/ivlab3_data/fwvio/results/p1_grade"
GRADES=["kaist_real_005","industrial_fog","precision_mems","general_imu"]
RES=4096; ML=np.pi*0.623803/RES; MR=np.pi*0.623095/RES
def yaw(q): return np.arctan2(2*(q[:,3]*q[:,2]+q[:,0]*q[:,1]),1-2*(q[:,1]**2+q[:,2]**2))
def wrap(a): return (a+np.pi)%(2*np.pi)-np.pi
def Rz(a): return np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
def ate(P,G):  # SE3 Umeyama (no scale), RMS pos err. P,G (n,3)
    mp,mg=P.mean(0),G.mean(0); Pc,Gc=P-mp,G-mg; C=Gc.T@Pc/len(P)
    U,_,Vt=np.linalg.svd(C); R=U@Vt
    if np.linalg.det(R)<0: U[:,-1]*=-1; R=U@Vt
    Pal=(R@P.T).T+(mg-R@mp); return np.sqrt(((Pal-G)**2).sum(1).mean())
def reintegrate(p0, yaws, dbody):  # yaws (n,), dbody (n-1,3) body increments -> positions (n,3)
    P=np.zeros((len(yaws),3)); P[0]=p0
    for i in range(len(yaws)-1):
        d=dbody[i].copy(); xy=Rz(yaws[i])@d[:2]; P[i+1]=P[i]+np.array([xy[0],xy[1],d[2]])
    return P
def fogoff(seq):
    for c in [f"{P1G}/{seq}/fogoff_rep0/vio.tum",f"{P1F}/{seq}/imu_rep0/vio.tum",f"{P1F}/{seq}/imu_rep1/vio.tum"]:
        if os.path.exists(c) and os.path.getsize(c)>100: return c
    return None
def baseline_tum(seq,grade):
    for c in [f"{P1G}/{seq}/{grade}_rep0/vio.tum", f"{P1F}/{seq}/fog_rep0/vio.tum"]:
        if os.path.exists(c) and os.path.getsize(c)>100: return c
    return None

def run(seq,grade):
    bt=baseline_tum(seq,grade); fo=fogoff(seq)
    if not bt or not fo: return None
    b=np.loadtxt(bt); tb=b[:,0]; pb=b[:,1:4]; yb=np.unwrap(yaw(b[:,4:8]))
    if len(tb)<6: return None
    gt=np.loadtxt(f"{EXT}/{seq}/pose/{seq}/global_pose.tum"); gts=gt[:,0]
    g_at=np.column_stack([np.interp(tb,gts,gt[:,1]),np.interp(tb,gts,gt[:,2]),np.interp(tb,gts,gt[:,3])])
    gyaw=np.unwrap(yaw(gt[:,4:8])); gy_at=np.interp(tb,gts,gyaw)
    # baseline body increments (yaw-only un-rotate; keep z)
    dw=np.diff(pb,axis=0); dbody=np.zeros_like(dw)
    for i in range(len(dw)): xy=Rz(-yb[i])@dw[i,:2]; dbody[i]=[xy[0],xy[1],dw[i,2]]
    # increments on baseline grid
    dgt=wrap(np.diff(gy_at)); dvis_y=wrap(np.diff(np.interp(tb,np.loadtxt(fo)[:,0],np.unwrap(yaw(np.loadtxt(fo)[:,4:8])))))
    sd=f"{EXT}/{seq}/data/{seq}/sensor_data"; fc=f"{sd}/fog.csv" if grade=="kaist_real_005" else f"{sd}/fog_grade_{grade}.csv"
    f=np.loadtxt(fc,delimiter=","); cum=np.cumsum(f[:,3]); dfog=wrap(np.diff(np.interp(tb,f[:,0]*1e-9,cum)))
    s=np.sign(np.corrcoef(dfog,dgt)[0,1]); dfog*=s
    # ORACLE yaw increments (best of fog/vis per interval vs GT)
    ef=np.abs(dfog-dgt); ev=np.abs(dvis_y-dgt); dpsi_or=np.where(ef<=ev,dfog,dvis_y)
    y_oracle=np.concatenate([[yb[0]], yb[0]+np.cumsum(dpsi_or)])
    # ORACLE translation: wheel vs baseline-vision per interval (distance)
    enc=np.loadtxt(f"{sd}/encoder.csv",delimiter=","); ets=enc[:,0]*1e-9
    l=np.interp(tb,ets,enc[:,1]); r=np.interp(tb,ets,enc[:,2]); fwd=0.5*(np.abs(np.diff(l))*ML+np.abs(np.diff(r))*MR)
    dist_gt=np.hypot(np.diff(g_at[:,0]),np.diff(g_at[:,1])); dist_vis=np.hypot(dbody[:,0],dbody[:,1])
    ew=np.abs(fwd-dist_gt); evt=np.abs(dist_vis-dist_gt)
    dbody_or=dbody.copy()
    for i in range(len(dbody)):
        if ew[i]<evt[i]: dbody_or[i]=[fwd[i],0.0,dbody[i,2]]   # wheel: forward only in body
    # reconstruct + ATE
    P_base=reintegrate(pb[0], yb, dbody)
    P_fog =reintegrate(pb[0], y_oracle, dbody)
    P_whl =reintegrate(pb[0], yb, dbody_or)
    A_base=ate(P_base,g_at); A_fog=ate(P_fog,g_at); A_whl=ate(P_whl,g_at)
    return dict(base=A_base, fog=A_fog, whl=A_whl,
                fog_redux=100*(A_base-A_fog)/max(A_base,1e-9), whl_redux=100*(A_base-A_whl)/max(A_base,1e-9))

if __name__=="__main__":
    seqs=sys.argv[1:] or ["urban28-pankyo","urban29-pankyo","urban26-dongtan","urban27-dongtan"]
    print(f"{'seq':16}{'grade':16}{'ATE_base':>9}{'ATE_FOGor':>10}{'FOGredux%':>10}{'ATE_WHLor':>10}{'WHLredux%':>10}")
    for s in seqs:
        for g in GRADES:
            r=run(s,g)
            if r is None: print(f"{s:16}{g:16}  (skip/missing)"); continue
            print(f"{s:16}{g:16}{r['base']:>9.3f}{r['fog']:>10.3f}{r['fog_redux']:>10.1f}{r['whl']:>10.3f}{r['whl_redux']:>10.1f}")
        print()
