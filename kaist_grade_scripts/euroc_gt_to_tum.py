#!/usr/bin/env python3
"""EuRoC state_groundtruth_estimate0/data.csv -> TUM (ts_sec x y z qx qy qz qw). ts in SECONDS to match VINS Headers."""
import sys, numpy as np
inp, out = sys.argv[1], sys.argv[2]
a = np.loadtxt(inp, delimiter=",", comments="#")
# cols: ts_ns, px,py,pz, qw,qx,qy,qz, vx,vy,vz, bwx..., bax...
ts = a[:,0]*1e-9; p = a[:,1:4]; qw=a[:,4]; qx=a[:,5]; qy=a[:,6]; qz=a[:,7]
out_arr = np.column_stack([ts, p[:,0],p[:,1],p[:,2], qx,qy,qz,qw])
np.savetxt(out, out_arr, fmt="%.9f", header="ts x y z qx qy qz qw", comments="# ")
print(f"wrote {out} n={len(out_arr)} dur={ts[-1]-ts[0]:.0f}s")
