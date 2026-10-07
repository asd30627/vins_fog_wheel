#!/usr/bin/env python3
"""JOINT all-sensor oracle ceiling (rotation AND translation simultaneously best-of), Curve-1 easy seqs.
Per keyframe interval, on the Curve-1 (FOG-aided) baseline grid:
  rotation    : pick per-interval min(|FOG_integ - GT|, |FOG-off-VINS_yaw - GT|)
  translation : pick per-interval min(|wheel_integ - GT|, |FOG-off-VINS_trans - GT|)
  -> reintegrate ONE trajectory with BOTH oracle selections -> position ATE (SE3 Umeyama, no scale).
Report per (seq,grade): ATE_base (Curve-1 FOG-aided) vs ATE_joint vs improvement%. Also FOG-only / wheel-only for context.
⚠ Oracle SELECTION uses GT, and KAIST GT fuses wheel+FOG (circular) -> ATE_joint is an OPTIMISTIC UPPER BOUND (ceiling)."""
import numpy as np, os, sys
EXT="/mnt/sata4t/datasets/kaist_complex_urban/extracted"
P1F="/mnt/sata4t/ivlab3_data/fwvio/results/p1_factors"; P1G="/mnt/sata4t/ivlab3_data/fwvio/results/p1_grade"
GRADES=["kaist_real_005","industrial_fog","precision_mems","general_imu"]
RES=4096; ML=np.pi*0.623803/RES; MR=np.pi*0.623095/RES
def yaw(q): return np.arctan2(2*(q[:,3]*q[:,2]+q[:,0]*q[:,1]),1-2*(q[:,1]**2+q[:,2]**2))
def wrap(a): return (a+np.pi)%(2*np.pi)-np.pi
def Rz(a): return np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
def ate(P,G):
    mp,mg=P.mean(0),G.mean(0); Pc,Gc=P-mp,G-mg; C=Gc.T@Pc/len(P)
    U,_,Vt=np.linalg.svd(C); R=U@Vt
    if np.linalg.det(R)<0: U[:,-1]*=-1; R=U@Vt
    Pal=(R@P.T).T+(mg-R@mp); return np.sqrt(((Pal-G)**2).sum(1).mean())
def reintegrate(p0,yaws,dbody):
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
    # baseline body increments (yaw-only un-rotate; keep z) — the recomposition base
    dw=np.diff(pb,axis=0); dbody=np.zeros_like(dw)
    for i in range(len(dw)): xy=Rz(-yb[i])@dw[i,:2]; dbody[i]=[xy[0],xy[1],dw[i,2]]
    dgt=wrap(np.diff(gy_at))
    # FOG-off VINS on baseline grid
    fov=np.loadtxt(fo); foy=np.unwrap(yaw(fov[:,4:8]))
    dvis_y=wrap(np.diff(np.interp(tb,fov[:,0],foy)))
    # FOG integrated yaw increments
    sd=f"{EXT}/{seq}/data/{seq}/sensor_data"; fc=f"{sd}/fog.csv" if grade=="kaist_real_005" else f"{sd}/fog_grade_{grade}.csv"
    f=np.loadtxt(fc,delimiter=","); cum=np.cumsum(f[:,3]); dfog=wrap(np.diff(np.interp(tb,f[:,0]*1e-9,cum)))
    dfog*=np.sign(np.corrcoef(dfog,dgt)[0,1])
    # --- ROTATION oracle: best of FOG vs FOG-off-VINS yaw ---
    ef=np.abs(dfog-dgt); ev=np.abs(dvis_y-dgt); dpsi_or=np.where(ef<=ev,dfog,dvis_y)
    y_oracle=np.concatenate([[yb[0]], yb[0]+np.cumsum(dpsi_or)])
    y_fogonly=y_oracle  # rotation-only oracle uses same selection
    # --- TRANSLATION oracle: best of wheel vs vision(baseline) forward distance ---
    enc=np.loadtxt(f"{sd}/encoder.csv",delimiter=","); ets=enc[:,0]*1e-9
    l=np.interp(tb,ets,enc[:,1]); r=np.interp(tb,ets,enc[:,2]); fwd=0.5*(np.abs(np.diff(l))*ML+np.abs(np.diff(r))*MR)
    dist_gt=np.hypot(np.diff(g_at[:,0]),np.diff(g_at[:,1])); dist_vis=np.hypot(dbody[:,0],dbody[:,1])
    ew=np.abs(fwd-dist_gt); evt=np.abs(dist_vis-dist_gt)
    dbody_or=dbody.copy()
    for i in range(len(dbody)):
        if ew[i]<evt[i]: dbody_or[i]=[fwd[i],0.0,dbody[i,2]]
    # --- reconstruct: base / FOG-only / wheel-only / JOINT ---
    P_base =reintegrate(pb[0], yb,       dbody)
    P_fog  =reintegrate(pb[0], y_oracle, dbody)
    P_whl  =reintegrate(pb[0], yb,       dbody_or)
    P_joint=reintegrate(pb[0], y_oracle, dbody_or)   # BOTH oracle selections
    A_base=ate(P_base,g_at); A_fog=ate(P_fog,g_at); A_whl=ate(P_whl,g_at); A_joint=ate(P_joint,g_at)
    red=lambda a:100*(A_base-a)/max(A_base,1e-9)
    return dict(base=A_base,fog=A_fog,whl=A_whl,joint=A_joint,
                fog_r=red(A_fog),whl_r=red(A_whl),joint_r=red(A_joint))

if __name__=="__main__":
    seqs=sys.argv[1:] or ["urban28-pankyo","urban29-pankyo","urban26-dongtan","urban27-dongtan"]
    print("⚠ oracle uses GT (KAIST GT fuses FOG+wheel -> circular) => JOINT ATE is OPTIMISTIC UPPER BOUND.\n")
    print(f"{'seq':16}{'grade':16}{'ATE_base':>9}{'ATE_FOGonly':>12}{'ATE_WHLonly':>12}{'ATE_JOINT':>11}{'JOINT_redux%':>13}")
    rows=[]
    for s in seqs:
        for g in GRADES:
            r=run(s,g)
            if r is None: print(f"{s:16}{g:16}  (skip/missing)"); continue
            rows.append((s,g,r))
            print(f"{s:16}{g:16}{r['base']:>9.2f}{r['fog']:>12.2f}{r['whl']:>12.2f}{r['joint']:>11.2f}{r['joint_r']:>13.1f}")
        print()
    if rows:
        jr=[r['joint_r'] for _,_,r in rows]
        print(f"JOINT redux% across {len(rows)} (seq,grade): median={np.median(jr):.1f}  min={min(jr):.1f}  max={max(jr):.1f}")
