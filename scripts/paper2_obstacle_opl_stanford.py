#!/usr/bin/env python3
"""
Phase 1.3 + 3.1 (obstacle channel): instantiate the integrity formalism
(Protection Level / Alert Limit / Stanford integrity diagram) on the
obstacle-state channel.  OFFLINE ONLY.  No CARLA/VINS, no estimator/planner edits.

OPL = calibrated per-object upper bound on instantaneous true error, computed
from RUNTIME-observable features only (NOT true error, NOT GT).

Approach: split-conformal quantile regression.
  1. Train GradientBoostingRegressor(loss='quantile', alpha=1-IR) on split=train.
  2. Split-conformal correction on a calibration set:
        s_i = err_i - qhat(x_i)               (conformity score)
        Q   = ceil((1-IR)(n+1))/n quantile of {s_i}
        OPL(x) = qhat(x) + Q
     -> finite-sample marginal coverage P(err<=OPL) >= 1-IR.
  3. Evaluate exceedance + Stanford regions on held-out test.

Alert limits (FIXED, frozen before results, from obstacle-state-integrity spec):
  position AL = 3 m , velocity AL = 3 m/s.  NOT re-tuned post-hoc.
"""
import os, json, warnings
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.ensemble import GradientBoostingRegressor

RNG = np.random.RandomState(0)
OUT = '/home/ivlab3/fwvio_estimator_ws_wheel/logs/obstacle_opl'
os.makedirs(OUT, exist_ok=True)

AL = {'position': 3.0, 'velocity': 3.0}          # FIXED alert limits
IR_LIST = [0.05, 0.10, 0.20]
IR_MAIN = 0.10                                    # candidate target IR (headline)
# a "stricter bound" for the MI region: PL between AL and MI_FACTOR*AL is 'available/MI'.
MI_FACTOR = 2.0

# ------------------------------------------------------------------ conformal
def conformal_opl(Xtr, ytr, Xcal, ycal, Xte, ir):
    """Return OPL predictions on cal and test via split-conformal quantile reg."""
    q = 1.0 - ir
    gbr = GradientBoostingRegressor(loss='quantile', alpha=q,
                                    n_estimators=300, max_depth=3,
                                    learning_rate=0.05, subsample=0.8,
                                    random_state=0)
    gbr.fit(Xtr, ytr)
    qcal = gbr.predict(Xcal)
    s = ycal - qcal                                  # conformity score
    n = len(s)
    k = int(np.ceil(q * (n + 1)))
    k = min(max(k, 1), n)
    Q = np.sort(s)[k - 1]                             # k-th smallest
    opl_cal = np.clip(qcal + Q, 0, None)
    opl_te = np.clip(gbr.predict(Xte) + Q, 0, None)
    return opl_te, opl_cal, Q, gbr

# ------------------------------------------------------------------ regions
def stanford_regions(err, pl, al, mi_hi):
    """Classify each sample into nominal / available / MI / HMI.
       nominal   : err < al  and pl < al          (correctly declared safe)
       available : err < al  and pl >= al         (false alert - availability cost)
       MI        : err >= al and pl >= al and pl < mi_hi   (flagged, misleading-ish upper zone)
       HMI       : err >= al and pl < al          (FALSE-SAFE / hazardously misleading)
       For the classic Stanford diagram the fault-detected zone above y=x is
       'system available/MI'; only points with err>=AL and pl<AL are HMI.
    """
    err = np.asarray(err); pl = np.asarray(pl)
    nominal = (err < al) & (pl < al)
    avail   = (err < al) & (pl >= al)
    hmi     = (err >= al) & (pl < al)
    mi      = (err >= al) & (pl >= al)            # detected unsafe (safe outcome integrity-wise)
    return dict(nominal=int(nominal.sum()), available=int(avail.sum()),
                MI=int(mi.sum()), HMI=int(hmi.sum()))

# ------------------------------------------------------------------ baselines
def baseline_constant_pl(err_cal, ir):
    """Constant PL = (1-ir) empirical quantile of calibration error (no features)."""
    return float(np.quantile(err_cal, 1 - ir))

def baseline_distance_gate(range_cal, err_cal, al, ir):
    """Distance-gate PL: accept (PL small ~0) only if range < X*, else PL=huge.
       Choose X* on calibration as largest range s.t. accepted-set exceedance<=ir;
       within accepted set assign PL = (1-ir) quantile of accepted err (so it can
       still breach), outside set PL = large (always flagged)."""
    order = np.argsort(range_cal)
    r_sorted = np.asarray(range_cal)[order]
    e_sorted = np.asarray(err_cal)[order]
    best_X = 0.0
    # scan candidate cutoffs; pick largest range keeping accepted exceedance<=ir
    cand = np.unique(np.quantile(r_sorted, np.linspace(0.05, 1.0, 40)))
    for X in cand:
        acc = r_sorted <= X
        if acc.sum() < 20:
            continue
        exc = (e_sorted[acc] > al).mean()
        if exc <= ir:
            best_X = X
    return best_X

def apply_distance_gate(range_te, best_X, opl_accept):
    pl = np.where(np.asarray(range_te) <= best_X, opl_accept, 1e6)
    return pl

# ------------------------------------------------------------------ per-channel run
def run_channel(name, df_tr, df_cal, df_te, feats, errcol, al, ir):
    Xtr, ytr = df_tr[feats].values, df_tr[errcol].values
    Xcal, ycal = df_cal[feats].values, df_cal[errcol].values
    Xte, yte = df_te[feats].values, df_te[errcol].values
    opl_te, opl_cal, Q, gbr = conformal_opl(Xtr, ytr, Xcal, ycal, Xte, ir)

    # calibration verification (held-out test exceedance)
    exceed = float((yte > opl_te).mean())
    mi_hi = MI_FACTOR * al
    reg = stanford_regions(yte, opl_te, al, mi_hi)
    n = len(yte)
    # HMI (false-safe) rate = HMI / N ; availability cost = false-alert / (err<al)
    hmi_rate = reg['HMI'] / n
    unsafe = (yte >= al)
    detected_unsafe = reg['MI']
    hmi_among_unsafe = reg['HMI'] / max(unsafe.sum(), 1)
    safe = (yte < al)
    false_alert_rate = reg['available'] / max(safe.sum(), 1)
    # availability = fraction declared safe (pl<al)
    availability = float((opl_te < al).mean())

    # ---- baselines at same IR ----
    # constant PL
    c_pl = baseline_constant_pl(ycal, ir)
    c_reg = stanford_regions(yte, np.full(n, c_pl), al, mi_hi)
    c_hmi = c_reg['HMI'] / max(unsafe.sum(), 1)
    c_fa = c_reg['available'] / max(safe.sum(), 1)
    c_avail = float((c_pl < al))  # constant -> all-or-nothing
    # distance-gate PL (needs a 'range' feature)
    rcol = 'range_m'
    if rcol in df_cal.columns:
        bestX = baseline_distance_gate(df_cal[rcol].values, ycal, al, ir)
        # accepted objects get a small PL = (1-ir) quantile of accepted-cal err
        acc_cal = df_cal[rcol].values <= bestX
        opl_acc = float(np.quantile(ycal[acc_cal], 1 - ir)) if acc_cal.sum() > 10 else al * 0.5
        dg_pl = apply_distance_gate(df_te[rcol].values, bestX, opl_acc)
        dg_reg = stanford_regions(yte, dg_pl, al, mi_hi)
        dg_hmi = dg_reg['HMI'] / max(unsafe.sum(), 1)
        dg_fa = dg_reg['available'] / max(safe.sum(), 1)
        dg_avail = float((dg_pl < al).mean())
    else:
        bestX = None; dg_hmi = dg_fa = dg_avail = float('nan')

    row = dict(channel=name, ir=ir, n_test=n, Q=float(Q),
               empirical_exceedance=exceed, target_ir=ir,
               calibrated=(exceed <= ir + 0.02),
               HMI_rate_overall=hmi_rate,
               HMI_rate_among_unsafe=hmi_among_unsafe,
               availability=availability,
               false_alert_rate=false_alert_rate,
               **{f'reg_{k}': v for k, v in reg.items()},
               base_const_HMI_among_unsafe=c_hmi, base_const_availability=c_avail,
               base_const_false_alert=c_fa, base_const_pl=c_pl,
               base_dist_HMI_among_unsafe=dg_hmi, base_dist_availability=dg_avail,
               base_dist_false_alert=dg_fa, base_dist_cutoff=bestX)
    return row, yte, opl_te, reg

# ------------------------------------------------------------------ diagram
def stanford_diagram(name, err, pl, al, path, mi_hi):
    err = np.asarray(err); pl = np.asarray(pl)
    fig, ax = plt.subplots(figsize=(6.2, 6))
    lim = np.nanpercentile(np.concatenate([err, pl]), 99.5)
    lim = max(lim, al * 2.5)
    # shade HMI region: err>=al & pl<al  (lower-right)  -> danger
    ax.axhspan(0, al, xmin=al / lim, xmax=1.0, color='red', alpha=0.10, zorder=0)
    ax.axvline(al, color='k', ls='--', lw=1); ax.axhline(al, color='k', ls='--', lw=1)
    ax.plot([0, lim], [0, lim], color='gray', ls=':', lw=1, label='PL = error')
    # colour points by region
    nominal = (err < al) & (pl < al)
    avail = (err < al) & (pl >= al)
    hmi = (err >= al) & (pl < al)
    mi = (err >= al) & (pl >= al)
    ax.scatter(err[nominal], pl[nominal], s=4, c='#2ca02c', alpha=.35, label=f'nominal ({nominal.sum()})')
    ax.scatter(err[avail], pl[avail], s=4, c='#1f77b4', alpha=.35, label=f'false-alert ({avail.sum()})')
    ax.scatter(err[mi], pl[mi], s=4, c='#ff7f0e', alpha=.35, label=f'detected-unsafe/MI ({mi.sum()})')
    ax.scatter(err[hmi], pl[hmi], s=8, c='red', alpha=.7, marker='x', label=f'HMI false-safe ({hmi.sum()})')
    ax.set_xlim(0, lim); ax.set_ylim(0, lim)
    ax.set_xlabel('true error'); ax.set_ylabel('protection level (OPL)')
    ax.set_title(f'Stanford integrity diagram: {name}\nAL={al}')
    ax.legend(loc='upper right', fontsize=7, framealpha=.9)
    fig.tight_layout(); fig.savefig(path, dpi=120); plt.close(fig)

# ================================================================== DATA PREP
def prep_carla():
    df = pd.read_parquet('/home/ivlab3/fwvio_estimator_ws_wheel/paper2_v5_validity_with_ovi.parquet')
    feats = ['range_m', 'depth_noise', 'log_range', 'yaw_lever', 'bearing_change_rate']
    df = df.dropna(subset=feats + ['pos_err_m', 'speed_err_ms']).reset_index(drop=True)
    tr = df[df.split == 'train'].reset_index(drop=True)
    te = df[df.split == 'test'].reset_index(drop=True)
    # carve a calibration set from train by scene (town,run) to avoid leak
    grp = tr.groupby(['town', 'run']).ngroup()
    ug = np.unique(grp); RNG.shuffle(ug)
    cal_g = set(ug[:max(1, len(ug) // 4)])
    cal = tr[grp.isin(cal_g)].reset_index(drop=True)
    trn = tr[~grp.isin(cal_g)].reset_index(drop=True)
    return trn, cal, te, feats

def prep_kitti():
    df = pd.read_csv('/home/ivlab3/fwvio_estimator_ws_wheel/paper2/paper2_kitti_validity_dataset.csv')
    feats = ['range_m', 'depth_m', 'bbox_h', 'bbox_w', 'bbox_area', 'det_conf',
             'bearing_deg', 'iou', 'trunc', 'occ']
    # position channel: all rows with pos_err
    df_pos = df.dropna(subset=feats + ['pos_err_m']).reset_index(drop=True)
    # velocity channel: only rows with a velocity estimate
    df_vel = df[df.has_vel == 1].dropna(subset=feats + ['vel_err_ms']).reset_index(drop=True)
    # grouped split by seq: 60/20/20 train/cal/test
    def split_by_seq(d):
        seqs = np.array(sorted(d.seq.unique())); RNG.shuffle(seqs)
        nte = max(1, int(round(0.2 * len(seqs))))
        ncal = max(1, int(round(0.2 * len(seqs))))
        te_s = set(seqs[:nte]); cal_s = set(seqs[nte:nte + ncal])
        tr_s = set(seqs[nte + ncal:])
        return (d[d.seq.isin(tr_s)].reset_index(drop=True),
                d[d.seq.isin(cal_s)].reset_index(drop=True),
                d[d.seq.isin(te_s)].reset_index(drop=True))
    return feats, split_by_seq(df_pos), split_by_seq(df_vel)

# ================================================================== MAIN
def main():
    results = []
    region_rows = []
    diagrams = {}

    # ---------- CARLA ----------
    ctr, ccal, cte, cfeats = prep_carla()
    for ir in IR_LIST:
        r, err, pl, reg = run_channel('CARLA-position', ctr, ccal, cte, cfeats, 'pos_err_m', AL['position'], ir)
        results.append(r)
        if ir == IR_MAIN:
            diagrams['CARLA-position'] = (err, pl, AL['position'])
            region_rows.append(dict(dataset='CARLA', channel='position', ir=ir, **reg, n=len(err)))
        r2, err2, pl2, reg2 = run_channel('CARLA-velocity', ctr, ccal, cte, cfeats, 'speed_err_ms', AL['velocity'], ir)
        results.append(r2)
        if ir == IR_MAIN:
            diagrams['CARLA-velocity'] = (err2, pl2, AL['velocity'])
            region_rows.append(dict(dataset='CARLA', channel='velocity', ir=ir, **reg2, n=len(err2)))

    # ---------- KITTI ----------
    kfeats, (kp_tr, kp_cal, kp_te), (kv_tr, kv_cal, kv_te) = prep_kitti()
    for ir in IR_LIST:
        r, err, pl, reg = run_channel('KITTI-position', kp_tr, kp_cal, kp_te, kfeats, 'pos_err_m', AL['position'], ir)
        results.append(r)
        if ir == IR_MAIN:
            diagrams['KITTI-position'] = (err, pl, AL['position'])
            region_rows.append(dict(dataset='KITTI', channel='position', ir=ir, **reg, n=len(err)))
        r2, err2, pl2, reg2 = run_channel('KITTI-velocity', kv_tr, kv_cal, kv_te, kfeats, 'vel_err_ms', AL['velocity'], ir)
        results.append(r2)
        if ir == IR_MAIN:
            diagrams['KITTI-velocity'] = (err2, pl2, AL['velocity'])
            region_rows.append(dict(dataset='KITTI', channel='velocity', ir=ir, **reg2, n=len(err2)))

    # ---------- DIAGNOSTIC: KITTI conformal under RANDOM (exchangeable) split ----------
    # isolates 'is the conformal machinery calibrated?' from 'does cross-scene shift break it?'
    diag = []
    kd = pd.read_csv('/home/ivlab3/fwvio_estimator_ws_wheel/paper2/paper2_kitti_validity_dataset.csv')
    for chan, errc, hasvel in [('KITTI-position', 'pos_err_m', False), ('KITTI-velocity', 'vel_err_ms', True)]:
        d = kd[kd.has_vel == 1] if hasvel else kd
        d = d.dropna(subset=kfeats + [errc]).reset_index(drop=True)
        idx = np.arange(len(d)); RNG.shuffle(idx)
        a, b = int(.6 * len(d)), int(.8 * len(d))
        tr, cal, tey = d.iloc[idx[:a]], d.iloc[idx[a:b]], d.iloc[idx[b:]]
        for ir in IR_LIST:
            opl_te, _, Q, _ = conformal_opl(tr[kfeats].values, tr[errc].values,
                                            cal[kfeats].values, cal[errc].values,
                                            tey[kfeats].values, ir)
            diag.append(dict(channel=chan, split='random_exchangeable', ir=ir,
                             empirical_exceedance=float((tey[errc].values > opl_te).mean())))
    pd.DataFrame(diag).to_csv(f'{OUT}/kitti_random_split_calibration.csv', index=False)

    res = pd.DataFrame(results)
    res.to_csv(f'{OUT}/opl_results_all_ir.csv', index=False)
    pd.DataFrame(region_rows).to_csv(f'{OUT}/stanford_region_counts.csv', index=False)
    print('\n===== KITTI conformal under RANDOM (exchangeable) split =====')
    print(pd.DataFrame(diag).round(4).to_string(index=False))

    # diagrams at IR_MAIN
    for nm, (err, pl, al) in diagrams.items():
        stanford_diagram(nm, err, pl, al, f'{OUT}/stanford_{nm.replace("-", "_")}.png', MI_FACTOR * al)

    # ---- console dump ----
    pd.set_option('display.width', 220, 'display.max_columns', 60)
    print('\n===== OPL RESULTS (all IR) =====')
    show = ['channel', 'ir', 'n_test', 'empirical_exceedance', 'calibrated',
            'HMI_rate_among_unsafe', 'availability', 'false_alert_rate',
            'base_const_HMI_among_unsafe', 'base_const_availability',
            'base_dist_HMI_among_unsafe', 'base_dist_availability', 'base_dist_cutoff']
    print(res[show].round(4).to_string(index=False))
    print('\n===== REGION COUNTS @ IR=%.2f =====' % IR_MAIN)
    print(pd.DataFrame(region_rows).to_string(index=False))
    res.to_json(f'{OUT}/opl_results_all_ir.json', orient='records', indent=2)
    print('\nWROTE:', OUT)

if __name__ == '__main__':
    main()
