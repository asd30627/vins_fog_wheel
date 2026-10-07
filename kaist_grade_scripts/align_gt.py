#!/usr/bin/env python3
"""Align a GT trajectory into the VINS world frame (SE3 Umeyama, no scale) so the 15-dim IMU-cov oracle's
gravity-dependent residual terms (position/velocity) are computed in the SAME frame as the VINS states.
Without this, GT (Vicon/global) frame != VINS gravity-aligned frame -> r_p/r_v garbage -> oracle hurts.
Args: vio.tum  gt.tum  out_aligned.tum   (TUM: ts x y z qx qy qz qw, ts in seconds)"""
import sys, numpy as np
vio_p, gt_p, out_p = sys.argv[1], sys.argv[2], sys.argv[3]
v = np.loadtxt(vio_p); g = np.loadtxt(gt_p)
vt, vp = v[:,0], v[:,1:4]; gt, gp, gq = g[:,0], g[:,1:4], g[:,4:8]
# GT positions at vio timestamps (nearest)
idx = np.clip(np.searchsorted(gt, vt), 0, len(gt)-1)
gp_at = gp[idx]
# Umeyama SE3 (no scale): find R,t s.t. vp ~= R*gp_at + t
mv, mg = vp.mean(0), gp_at.mean(0)
Vc, Gc = vp - mv, gp_at - mg
C = Vc.T @ Gc / len(vp)
U,_,Wt = np.linalg.svd(C); D = np.eye(3)
if np.linalg.det(U@Wt) < 0: D[2,2] = -1
R = U @ D @ Wt; t = mv - R @ mg
# apply to ALL GT poses: pos' = R*pos + t ; quat' = R_quat * q
def quat_mul(q1, q2):  # (x,y,z,w)
    x1,y1,z1,w1=q1; x2,y2,z2,w2=q2
    return np.array([w1*x2+x1*w2+y1*z2-z1*y2, w1*y2-x1*z2+y1*w2+z1*x2,
                     w1*z2+x1*y2-y1*x2+z1*w2, w1*w2-x1*x2-y1*y2-z1*z2])
def R_to_quat(Rm):
    w=np.sqrt(max(0,1+Rm[0,0]+Rm[1,1]+Rm[2,2]))/2
    x=(Rm[2,1]-Rm[1,2])/(4*w); y=(Rm[0,2]-Rm[2,0])/(4*w); z=(Rm[1,0]-Rm[0,1])/(4*w)
    return np.array([x,y,z,w])
Rq = R_to_quat(R)
gp_al = (R @ gp.T).T + t
gq_al = np.array([quat_mul(Rq, q) for q in gq])
gq_al /= np.linalg.norm(gq_al, axis=1, keepdims=True)
out = np.column_stack([gt, gp_al, gq_al])
np.savetxt(out_p, out, fmt="%.9f", header="ts x y z qx qy qz qw", comments="# ")
err = np.sqrt(((((R@gp_at.T).T+t) - vp)**2).sum(1).mean())
print(f"aligned GT -> {out_p}  align_rmse={err:.3f}m  (R det={np.linalg.det(R):.3f})")
