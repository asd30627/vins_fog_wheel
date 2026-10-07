#!/usr/bin/env python3
"""CONTINUOUS alpha/beta oracle ceiling vs BINARY oracle — Curve-1 easy seqs (VIWO: FOG + wheel).

Per keyframe interval, instead of the binary best-of (FOG vs VIO rotation; wheel vs VIO translation),
search a CONTINUOUS blend on the grid {0,0.1,...,1.0}:
  rotation    : dpsi(a) = a*dFOG + (1-a)*dVIO_yaw          ; a* = argmin_a |dpsi(a) - dGT_yaw|
  translation : dbody(b) = b*[fwd,0,z] + (1-b)*[dx,dy,z]   ; b* = argmin_b |planar_dist(dbody(b)) - dGT_dist|
rotation a and translation b searched INDEPENDENTLY per interval. Recompose ONE trajectory with the
per-interval optimal (a*, b*) -> position ATE (SE3 Umeyama, no scale).

Binary oracle = the SAME search restricted to grid endpoints {0,1} (so continuous >= binary by construction).
Reports per (seq,grade): ATE_baseline, ATE_binary, ATE_continuous, binary_improve%, continuous_improve%.
Also dumps the chosen a* / b* distribution (endpoint {0,1} vs interior fraction, histogram).

⚠ Oracle SELECTION uses GT; KAIST GT = RTK-GPS-dominated global_pose (FOG/wheel circularity small for this
  problem per task note) -> still an OPTIMISTIC UPPER BOUND, not an achievable value."""
import numpy as np, os, sys
EXT="/mnt/sata4t/datasets/kaist_complex_urban/extracted"
P1F="/mnt/sata4t/ivlab3_data/fwvio/results/p1_factors"; P1G="/mnt/sata4t/ivlab3_data/fwvio/results/p1_grade"
GRADES=["kaist_real_005","industrial_fog","precision_mems","general_imu"]
RES=4096; ML=np.pi*0.623803/RES; MR=np.pi*0.623095/RES
ALPHAS=np.round(np.arange(0,1.0001,0.1),3)   # 11 grid values 0,0.1,...,1.0
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

def run(seq,grade):
    bt=baseline_tum(seq,grade); fo=fogoff(seq)
    if not bt or not fo: return None
    b=np.loadtxt(bt); tb=b[:,0]; pb=b[:,1:4]; yb=np.unwrap(yaw(b[:,4:8]))
    if len(tb)<6: return None
    gt=np.loadtxt(f"{EXT}/{seq}/pose/{seq}/global_pose.tum"); gts=gt[:,0]
    g_at=np.column_stack([np.interp(tb,gts,gt[:,1]),np.interp(tb,gts,gt[:,2]),np.interp(tb,gts,gt[:,3])])
    gyaw=np.unwrap(yaw(gt[:,4:8])); gy_at=np.interp(tb,gts,gyaw)
    dw=np.diff(pb,axis=0); dbody=np.zeros_like(dw)
    for i in range(len(dw)): xy=Rz(-yb[i])@dw[i,:2]; dbody[i]=[xy[0],xy[1],dw[i,2]]
    dgt=wrap(np.diff(gy_at))
    fov=np.loadtxt(fo); foy=np.unwrap(yaw(fov[:,4:8]))
    dvis_y=wrap(np.diff(np.interp(tb,fov[:,0],foy)))
    sd=f"{EXT}/{seq}/data/{seq}/sensor_data"; fc=f"{sd}/fog.csv" if grade=="kaist_real_005" else f"{sd}/fog_grade_{grade}.csv"
    f=np.loadtxt(fc,delimiter=","); cum=np.cumsum(f[:,3]); dfog=wrap(np.diff(np.interp(tb,f[:,0]*1e-9,cum)))
    if np.std(dfog)>0 and np.std(dgt)>0: dfog*=np.sign(np.corrcoef(dfog,dgt)[0,1])
    # wheel forward distance + vision distance per interval
    enc=np.loadtxt(f"{sd}/encoder.csv",delimiter=","); ets=enc[:,0]*1e-9
    l=np.interp(tb,ets,enc[:,1]); r=np.interp(tb,ets,enc[:,2]); fwd=0.5*(np.abs(np.diff(l))*ML+np.abs(np.diff(r))*MR)
    dist_gt=np.hypot(np.diff(g_at[:,0]),np.diff(g_at[:,1]))
    n=len(dbody)
    # ---------- ROTATION: grid search a per interval ----------
    # dpsi(a) = a*dfog + (1-a)*dvis_y ; minimize |dpsi - dgt|
    cand_r=ALPHAS[:,None]*dfog[None,:]+(1-ALPHAS[:,None])*dvis_y[None,:]   # (11,n)
    err_r=np.abs(cand_r-dgt[None,:])
    ai=np.argmin(err_r,axis=0); a_star=ALPHAS[ai]               # continuous (full grid)
    # binary rotation = restrict to {0,1}: a in {0(VIO),1(FOG)}
    err_r_bin=np.vstack([err_r[0],err_r[-1]])                   # rows: a=0 (VIO), a=1 (FOG)
    abi=np.argmin(err_r_bin,axis=0); a_bin=abi.astype(float)    # 0 or 1
    dpsi_cont=cand_r[ai,np.arange(n)]
    dpsi_bin =np.where(a_bin==1.0,dfog,dvis_y)
    # ---------- TRANSLATION: grid search b per interval ----------
    # dbody(b) = b*[fwd,0,z] + (1-b)*[dx,dy,z]; minimize |planar_dist - dist_gt|
    wheel_vec=np.column_stack([fwd,np.zeros(n),dbody[:,2]])     # (n,3)
    vis_vec  =dbody                                             # (n,3)
    # blended planar distance for each b: (11,n)
    bx=ALPHAS[:,None]*wheel_vec[None,:,0]+(1-ALPHAS[:,None])*vis_vec[None,:,0]
    by=ALPHAS[:,None]*wheel_vec[None,:,1]+(1-ALPHAS[:,None])*vis_vec[None,:,1]
    dist_b=np.hypot(bx,by)                                      # (11,n)
    err_t=np.abs(dist_b-dist_gt[None,:])
    bi=np.argmin(err_t,axis=0); b_star=ALPHAS[bi]
    err_t_bin=np.vstack([err_t[0],err_t[-1]])                   # b=0 (VIO), b=1 (wheel)
    bbi=np.argmin(err_t_bin,axis=0); b_bin=bbi.astype(float)
    def blend_vec(bw):  # (n,) weights -> (n,3) blended body increments
        out=np.zeros((n,3))
        out[:,0]=bw*wheel_vec[:,0]+(1-bw)*vis_vec[:,0]
        out[:,1]=bw*wheel_vec[:,1]+(1-bw)*vis_vec[:,1]
        out[:,2]=dbody[:,2]
        return out
    dbody_cont=blend_vec(b_star); dbody_bin=blend_vec(b_bin)
    # ---------- recompose ----------
    y_cont=np.concatenate([[yb[0]], yb[0]+np.cumsum(dpsi_cont)])
    y_bin =np.concatenate([[yb[0]], yb[0]+np.cumsum(dpsi_bin)])
    P_base=reintegrate(pb[0], yb,     dbody)
    P_bin =reintegrate(pb[0], y_bin,  dbody_bin)
    P_cont=reintegrate(pb[0], y_cont, dbody_cont)
    A_base=ate(P_base,g_at); A_bin=ate(P_bin,g_at); A_cont=ate(P_cont,g_at)
    red=lambda a:100*(A_base-a)/max(A_base,1e-9)
    return dict(base=A_base,binary=A_bin,cont=A_cont,bin_r=red(A_bin),cont_r=red(A_cont),
                a_star=a_star,b_star=b_star,n=n)

def dist_summary(vals):
    vals=np.asarray(vals); n=len(vals)
    end=np.mean((vals==0.0)|(vals==1.0))*100
    interior=100-end
    h={f"{a:.1f}":int(np.sum(np.isclose(vals,a))) for a in ALPHAS}
    return end,interior,h

if __name__=="__main__":
    seqs=sys.argv[1:] or ["urban26-dongtan","urban27-dongtan","urban28-pankyo","urban29-pankyo"]
    print("# CONTINUOUS alpha/beta oracle vs BINARY oracle (Curve-1 easy seqs, VIWO). GT-selected => OPTIMISTIC UPPER BOUND.\n")
    print(f"{'seq':16}{'grade':16}{'ATE_base':>9}{'ATE_bin':>9}{'ATE_cont':>9}{'bin_imp%':>9}{'cont_imp%':>10}{'gap%':>7}")
    rows=[]
    allA=[]; allB=[]; perseqA={}; perseqB={}
    for s in seqs:
        for g in GRADES:
            r=run(s,g)
            if r is None: print(f"{s:16}{g:16}  (skip/missing)"); continue
            rows.append((s,g,r))
            gap=r['cont_r']-r['bin_r']
            print(f"{s:16}{g:16}{r['base']:>9.2f}{r['binary']:>9.2f}{r['cont']:>9.2f}{r['bin_r']:>9.1f}{r['cont_r']:>10.1f}{gap:>7.1f}")
            allA.extend(r['a_star']); allB.extend(r['b_star'])
            perseqA.setdefault(s,[]).extend(r['a_star']); perseqB.setdefault(s,[]).extend(r['b_star'])
        print()
    if rows:
        br=[r['bin_r'] for _,_,r in rows]; cr=[r['cont_r'] for _,_,r in rows]; gp=[r['cont_r']-r['bin_r'] for _,_,r in rows]
        print(f"binary improve% across {len(rows)}: median={np.median(br):.1f} min={min(br):.1f} max={max(br):.1f}")
        print(f"continuous improve%        : median={np.median(cr):.1f} min={min(cr):.1f} max={max(cr):.1f}")
        print(f"gap (cont-bin)%            : median={np.median(gp):.1f} min={min(gp):.1f} max={max(gp):.1f}")
        print("\n## alpha (rotation FOG-weight) distribution")
        e,i,h=dist_summary(allA); print(f"ALL: endpoint{{0,1}}={e:.1f}%  interior={i:.1f}%  hist={h}")
        for s in perseqA:
            e,i,_=dist_summary(perseqA[s]); print(f"  {s:16} endpoint={e:.1f}% interior={i:.1f}%")
        print("\n## beta (translation wheel-weight) distribution")
        e,i,h=dist_summary(allB); print(f"ALL: endpoint{{0,1}}={e:.1f}%  interior={i:.1f}%  hist={h}")
        for s in perseqB:
            e,i,_=dist_summary(perseqB[s]); print(f"  {s:16} endpoint={e:.1f}% interior={i:.1f}%")
