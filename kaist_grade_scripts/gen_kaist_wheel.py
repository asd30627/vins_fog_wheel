#!/usr/bin/env python3
"""KAIST encoder.csv -> wheel preload CSV (ts_ns,dl,dr,df) for VINS wheel factor.
dl=Δleft_count*ML, dr=Δright_count*MR (per-wheel circumference/res), df=ds=(dl+dr)/2. Real encoder (noisy)."""
import sys,numpy as np
seq=sys.argv[1]; EXT="/mnt/sata4t/datasets/kaist_complex_urban/extracted"
sd=f"{EXT}/{seq}/data/{seq}/sensor_data"; enc=np.loadtxt(f"{sd}/encoder.csv",delimiter=",")
RES=4096; ML=np.pi*0.623803/RES; MR=np.pi*0.623095/RES
ts=enc[:,0].astype(np.int64); lc=enc[:,1]; rc=enc[:,2]
dl=np.diff(lc)*ML; dr=np.diff(rc)*MR; df=0.5*(dl+dr)
out=np.column_stack([ts[1:], dl, dr, df])
np.savetxt(f"{sd}/kaist_wheel.csv", out, delimiter=",", header="ts_ns,dl,dr,df", comments="", fmt=["%d","%.17g","%.17g","%.17g"])
print(f"wrote {sd}/kaist_wheel.csv n={len(out)}")
