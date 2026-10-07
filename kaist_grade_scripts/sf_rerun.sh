#!/usr/bin/env bash
# Re-run KAIST acc-bias-crash sequences with CARLA_SOFT_FAILURE=1 (skip reboot -> see if ba recovers / scale holds).
# Uses existing run_hard_one.sh (rep=sf -> separate dst). Default-OFF env so dataset runs untouched.
export CARLA_SOFT_FAILURE=1
export VINS_BIN_OVERRIDE=/home/ivlab3/fwvio_estimator_ws_wheel/install/vins/lib/vins/vins_node   # _wheel binary HAS soft-failure (non-wheel KAIST binary does NOT)
SP=/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts
GF=/home/ivlab3/miniconda3/envs/gf/bin/python
P1H=/mnt/sata4t/ivlab3_data/fwvio/results/p1_grade_hard
ROW=$SP/sf_rerun_rows.tsv
printf "seq\tgrade\tnkf_before\tnkf_after\tba_max\tn_above\trecover_frac\tba_end\tearly\tlate\tmech\n" > "$ROW"
# targets: seq grade
TARGETS=( "urban18-highway kaist_real_005" "urban19-highway kaist_real_005" "urban22-highway kaist_real_005" \
          "urban24-highway kaist_real_005" "urban30-gangnam kaist_real_005" "urban38-pankyo industrial_fog" )
for t in "${TARGETS[@]}"; do
  set -- $t; seq=$1 grade=$2
  echo "[sf] $seq / $grade  CARLA_SOFT_FAILURE=1  $(date +%H:%M:%S)"
  CARLA_SOFT_FAILURE=1 bash "$SP/run_hard_one.sh" "$seq" "$grade" sf > "$SP/sf_${seq}_${grade}.log" 2>&1
  D="$P1H/$seq/${grade}_repsf"
  # analyze
  $GF - "$seq" "$grade" "$D" "$ROW" <<'PY'
import sys,os,csv,numpy as np,pandas as pd
seq,grade,D,ROW=sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4]
EXT="/mnt/sata4t/datasets/kaist_complex_urban/extracted"
csv_p=f"{D}/reliability_features.csv"; vt_p=f"{D}/vio.tum"
nkf_after=0; ba_max=float('nan'); n_above=0; recover='-'; ba_end=float('nan'); early=float('nan'); late=float('nan'); mech='?'
if os.path.exists(csv_p):
    df=pd.read_csv(csv_p)
    if 'ba_norm' in df and len(df)>1:
        ba=df['ba_norm'].astype(float).values; nkf_after=len(ba); ba_max=float(np.nanmax(ba)); n_above=int((ba>2.5).sum()); ba_end=float(ba[-1])
        tr=np.where(ba>2.5)[0]
        if len(tr):
            after=ba[tr[0]+1:]; recover=f"{np.mean(after<2.5):.2f}" if len(after) else "0.00"
        else: recover="no-trig"
# scale early/late from vio vs GT
def speeds(vt):
    v=np.loadtxt(vt); ts=v[:,0]; p=v[:,1:4]
    sp=np.r_[0,np.linalg.norm(np.diff(p,axis=0),axis=1)/np.maximum(np.diff(ts),1e-3)]
    return ts,p,sp
try:
    ts,p,vsp=speeds(vt_p)
    gt=np.loadtxt(f"{EXT}/{seq}/pose/{seq}/global_pose.tum"); gts=gt[:,0]; gp=gt[:,1:4]
    gsp=np.r_[0,np.linalg.norm(np.diff(gp,axis=0),axis=1)/np.maximum(np.diff(gts),1e-3)]
    t0=ts[0]; rr=[]
    for i in range(len(ts)):
        gi=min(np.searchsorted(gts,ts[i]),len(gsp)-1)
        if gsp[gi]>0.3: rr.append((ts[i]-t0, vsp[i]/gsp[gi]))
    e=[r for t,r in rr if t<11]; l=[r for t,r in rr if t>20]
    early=float(np.median(e)) if e else float('nan'); late=float(np.median(l)) if l else float('nan')
except Exception as ex: pass
if nkf_after<50: mech="still-tiny(no-recover)"
elif n_above==0: mech="NO-TRIG-now"
elif (recover not in ('-','no-trig')) and float(recover)>0.5 and (late==late and 0.8<=late<=1.25): mech="FALSE-ALARM(recovered+scale-ok)"
elif (late==late and late>1.5): mech="real-divergence(scale-bad)"
else: mech="mixed"
open(ROW,'a').write(f"{seq}\t{grade}\t?\t{nkf_after}\t{ba_max:.2f}\t{n_above}\t{recover}\t{ba_end:.2f}\t{early:.3f}\t{late:.3f}\t{mech}\n")
print(f"  -> nkf={nkf_after} ba_max={ba_max:.2f} n>2.5={n_above} recover={recover} early={early:.2f} late={late:.2f} :: {mech}")
PY
done
echo "===== SF RERUN DONE $(date +%H:%M:%S) ====="
