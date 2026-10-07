#!/usr/bin/env python3
"""Step B: does adding TEMPORAL features (past-window aggregates, first differences, turn entry/exit phase)
make the optimal rotation-alpha class (VIO-win/Mixed/FOG-win) learnable across sequences (LOSO)?
Pure post-processing on the existing per-interval dump (alpha + instantaneous runtime features). No VINS,
no GT leakage (target alpha from GT; features are runtime VINS/scene signals). KAIST keyframes ~10Hz =>
window W=10 ~1s, W=30 ~3s. Compare instantaneous-only vs temporal; report Mixed recall (was 14%)."""
import numpy as np, pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import confusion_matrix, accuracy_score
CSV="/home/ivlab3/fwvio_estimator_ws_wheel/kaist_grade_scripts/alpha_viwo_intervals.csv"
D=pd.read_csv(CSV)
D=D[~((D.seq=="urban29-pankyo")&(D.grade=="general_imu"))].copy()   # drop RUN_ERROR
BASE=["vel_norm","yaw_rate","outlier_ratio","reproj_res","ba_norm","bg_norm","feat_mgr","solver_ms"]
TEMPO_SRC=["vel_norm","yaw_rate","outlier_ratio","reproj_res"]

def add_temporal(df):
    g=df.sort_index()  # already time-ordered within group
    for f in TEMPO_SRC:
        s=g[f]
        g[f+"_d1"]=s.diff().fillna(0.0)                                  # first difference
        g[f+"_rm10"]=s.rolling(10,min_periods=1).mean()                 # past ~1s mean
        g[f+"_rm30"]=s.rolling(30,min_periods=1).mean()                 # past ~3s mean
        g[f+"_rs10"]=s.rolling(10,min_periods=1).std().fillna(0.0)      # past ~1s std (volatility)
        g[f+"_dev10"]=s-g[f+"_rm10"]                                    # deviation from recent
        g[f+"_slope10"]=(s-s.shift(10)).fillna(0.0)/10.0               # trend over ~1s
    # turn entry/exit phase from yaw_rate
    yr=g["yaw_rate"]
    g["turn_phase"]=(yr-yr.rolling(30,min_periods=1).mean())            # >0 entering/in-turn vs recent baseline
    g["yaw_accel"]=yr.diff().diff().fillna(0.0)                         # 2nd diff
    g["abs_turn_slope"]=(yr-yr.shift(10)).abs().fillna(0.0)
    return g

D=D.groupby(["seq","grade"],group_keys=False).apply(add_temporal)
TEMPO=[c for c in D.columns if any(c.startswith(f+"_") for f in TEMPO_SRC)]+["turn_phase","yaw_accel","abs_turn_slope"]
def cls(a): return np.where(a<0.2,0,np.where(a>0.8,2,1))
D["y"]=cls(D["alpha"].values)
names={0:"VIO-win",1:"Mixed",2:"FOG-win"}; SEQS=sorted(D.seq.unique())

def loso(featset,model="logreg"):
    accs=[];majs=[];cm=np.zeros((3,3),int)
    for test in SEQS:
        tr=D[D.seq!=test]; te=D[D.seq==test]
        Xtr=tr[featset].values; Xte=te[featset].values; ytr=tr.y.values; yte=te.y.values
        m=np.isfinite(Xtr).all(1)&np.isfinite(ytr); mt=np.isfinite(Xte).all(1)
        if model=="logreg":
            sc=StandardScaler().fit(Xtr[m])
            clf=LogisticRegression(max_iter=2000,class_weight="balanced",multi_class="multinomial").fit(sc.transform(Xtr[m]),ytr[m])
            pred=clf.predict(sc.transform(Xte[mt]))
        else:
            clf=HistGradientBoostingClassifier(max_iter=300,class_weight="balanced",random_state=0).fit(Xtr[m],ytr[m])
            pred=clf.predict(Xte[mt])
        accs.append(accuracy_score(yte[mt],pred)); maj=np.bincount(ytr[m],minlength=3).argmax()
        majs.append((yte[mt]==maj).mean()); cm+=confusion_matrix(yte[mt],pred,labels=[0,1,2])
    rec={names[i]:cm[i,i]/max(cm[i].sum(),1) for i in range(3)}
    return np.mean(accs),np.mean(majs),rec,cm

INST=["vel_norm","yaw_rate","outlier_ratio","reproj_res"]
print(f"# total intervals = {len(D)}  features: instantaneous={len(INST)} temporal-added={len(TEMPO)}\n")
for tag,fs,mdl in [("INSTANTANEOUS (4 feat) logreg",INST,"logreg"),
                   ("INST+TEMPORAL logreg",INST+TEMPO,"logreg"),
                   ("INST+TEMPORAL histgb",INST+TEMPO,"histgb")]:
    acc,maj,rec,cm=loso(fs,mdl)
    print(f"## {tag}")
    print(f"   LOSO acc={acc:.3f}  majority-baseline={maj:.3f}")
    print(f"   recall: VIO-win={rec['VIO-win']:.2f}  Mixed={rec['Mixed']:.2f}  FOG-win={rec['FOG-win']:.2f}")
    print(f"   confusion[true x pred] {cm.tolist()}\n")
# Spearman of temporal features vs alpha (top 12)
print("## Spearman(alpha vs feature) — top temporal features")
res=[]
for f in INST+TEMPO:
    x=D["alpha"].values; y=D[f].values; ok=np.isfinite(x)&np.isfinite(y)
    if ok.sum()>100: rho,_=spearmanr(x[ok],y[ok]); res.append((f,rho))
for f,rho in sorted(res,key=lambda z:-abs(z[1]))[:12]: print(f"   {f:22}rho={rho:+.3f}")
