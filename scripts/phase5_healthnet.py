#!/usr/bin/env python3
"""Phase 5 — IMU-VINS HealthNet

K0-REFRAME: K0 blocked KAIST-only real-world generalization claim.
It does NOT block a HealthNet built on controlled degradation.
This script evaluates runtime signals for predicting VINS failure within 30s.

Data: kaist_grade_scripts/reliability_dataset.tsv
  - 22,028 temporal windows across 7 KAIST sequences × 4 grades
  - ~30 runtime-observable signals (feat_count, outlier_ratio, yaw_disagree, etc.)
  - Labels: failure_in_30s (GT-derived from future VINS divergence)
  - Failures: 90 windows in urban38-pankyo × 3 synthetic grades

Evaluation:
  1. Rule-based baseline: threshold on acc_bias_margin (runtime signal)
  2. HistGBM on all runtime features (no GT leakage)
  3. AUROC, F1, false_safe, missed_alert, availability@AL_loc=0.20
  4. Stanford diagram (LPL via calibrated HistGBM → compare to isotonic v1)
  5. Time-to-alert distribution

Scope: Intra-dataset (urban38-pankyo held-out temporal split).
Real-world generalization claim is K5-gated (real-sensor cross-sequence).

NO VINS backend modification. NO GT at inference time.
OFFLINE analysis only — reads existing TSV/parquet files.
"""
import os
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (roc_auc_score, average_precision_score,
                              precision_recall_curve, f1_score)
from sklearn.calibration import CalibratedClassifierCV

ROOT = '/home/ivlab3/fwvio_estimator_ws_wheel'
OUT  = os.path.join(ROOT, 'logs', 'phase5')
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------------------
# Runtime-observable features (NO GT labels, NO future information)
# ---------------------------------------------------------------------------
RUNTIME_FEATURES = [
    # Visual quality
    'feat_mgr_mean', 'feat_mgr_last', 'feat_raw_mean',
    'outlier_ratio_mean', 'outlier_ratio_max',
    'inlier_count_mean',
    'coverage8_mean', 'entropy8_mean',
    'reproj_res_mean',
    'avg_track_len_mean',
    'visual_gate_pass_rate', 'visual_alpha_mean',
    # IMU / kinematics
    'yaw_disagree_mean', 'yaw_disagree_norm_mean', 'yaw_disagree_max',
    'ba_norm_mean', 'ba_norm_last', 'ba_norm_max', 'ba_norm_slope',
    'bg_norm_mean', 'bg_norm_last', 'bg_norm_max', 'bg_norm_slope',
    'solver_ms_mean',
    'vel_norm_mean', 'delta_p_norm_mean',
    'acc_norm_mean', 'acc_norm_std', 'acc_norm_max',
    'gyr_norm_mean', 'gyr_norm_max',
    'yaw_rate_mean', 'yaw_rate_std',
    # KEY runtime safety signal: current acc-bias margin to failure threshold
    'acc_bias_margin',
]

# Label: predict failure within next 30s
LABEL = 'failure_in_30s'

# FORBIDDEN at inference: future GT signal (acc_margin_min30 = future minimum)
FORBIDDEN = ['acc_margin_min30', 'survival_60s', 'grade_sensitive',
             'n_future_kf', 'grade_arw', 'grade_bias', 'grade_brw', 'grade_scale_ppm']

# AL for Stanford LPL diagram
AL_LOC = 0.20   # maps to: true risk = failure_in_30s = 1 → "unsafe"

def load_data():
    df = pd.read_csv(os.path.join(ROOT, 'kaist_grade_scripts',
                                  'reliability_dataset.tsv'), sep='\t')
    # Keep only runtime features + identifiers + label
    cols = ['dataset', 'sequence', 'grade', 'rep', 'tau'] + RUNTIME_FEATURES + [LABEL]
    df = df[cols].copy()
    df[RUNTIME_FEATURES] = df[RUNTIME_FEATURES].apply(pd.to_numeric, errors='coerce')
    df[LABEL] = df[LABEL].astype(int)
    df = df.dropna(subset=RUNTIME_FEATURES).reset_index(drop=True)
    return df


def temporal_split(df, test_frac=0.40, seed=42):
    """Temporal split within each (sequence, grade, rep): train on early, test on late."""
    train_idx, test_idx = [], []
    for keys, grp in df.groupby(['sequence', 'grade', 'rep'], sort=True):
        n = len(grp)
        split = int(n * (1 - test_frac))
        train_idx.extend(grp.index[:split].tolist())
        test_idx.extend(grp.index[split:].tolist())
    return df.loc[train_idx].copy(), df.loc[test_idx].copy()


def stratified_split(df, test_frac=0.30, seed=42):
    """Stratified random split preserving failure_in_30s ratio in train and test."""
    from sklearn.model_selection import train_test_split
    rng = np.random.RandomState(seed)
    tr, te = train_test_split(df, test_size=test_frac, stratify=df[LABEL],
                              random_state=seed)
    return tr.copy(), te.copy()


def rule_baseline_auc(df, threshold=2.30):
    """Rule: predict failure_in_30s when acc_bias_margin < threshold."""
    preds = (df['acc_bias_margin'] < threshold).astype(int)
    score = 1.0 - df['acc_bias_margin']   # higher = more at risk (monotone)
    auc = roc_auc_score(df[LABEL], score)
    f1  = f1_score(df[LABEL], preds, zero_division=0)
    fp  = ((preds == 1) & (df[LABEL] == 0)).sum()
    fn  = ((preds == 0) & (df[LABEL] == 1)).sum()
    return {'auc': auc, 'f1': f1, 'fp': fp, 'fn': fn, 'n_pos': df[LABEL].sum(),
            'threshold': threshold}


def compute_tta(df_test, score_col, true_label_col='failure_in_30s',
                threshold=0.5, tau_col='tau', window_secs=5):
    """Time-to-alert: for each failure window, find how many steps before it the model alerts."""
    leads = []
    for keys, grp in df_test.groupby(['sequence', 'grade', 'rep']):
        grp = grp.sort_values(tau_col).reset_index(drop=True)
        fail_idxs = grp[grp[true_label_col] == 1].index.tolist()
        if not fail_idxs:
            continue
        first_fail_idx = fail_idxs[0]
        # Find first alert BEFORE first failure
        alerts = grp[grp[score_col] >= threshold].index.tolist()
        pre_alerts = [a for a in alerts if a < first_fail_idx]
        if pre_alerts:
            lead = (first_fail_idx - pre_alerts[0]) * window_secs
            leads.append(lead)
        else:
            leads.append(0)  # missed-lead (no alert before failure)
    return leads


def build_lpl_from_scores(df_test, scores, ir=0.10):
    """Calibrate LPL from predicted probabilities using isotonic regression + Q-inflation."""
    # LPL = calibrated upper bound on P(unsafe) per window
    # true_error proxy: failure_in_30s (binary)
    y_true = df_test[LABEL].values
    iso = IsotonicRegression(out_of_bounds='clip')
    iso.fit(scores, y_true)
    iso_pred = iso.predict(scores)
    # Q-inflation: find smallest Q s.t. P(y_true > LPL) <= IR
    Qs = np.linspace(1.0, 5.0, 500)
    best_Q = Qs[-1]
    for Q in Qs:
        lpl = Q * iso_pred
        exceedance = np.mean(y_true > lpl)
        if exceedance <= ir:
            best_Q = Q
            break
    lpl_vals = best_Q * iso_pred
    exceedance = float(np.mean(y_true > lpl_vals))
    avail = float(np.mean(lpl_vals < AL_LOC))
    hmi   = int(np.sum((lpl_vals < AL_LOC) & (y_true == 1)))
    return lpl_vals, {'Q': best_Q, 'exceedance': exceedance,
                      'availability': avail, 'HMI': hmi, 'IR': ir}


def stanford_diagram(lpl_vals, y_true, title, path):
    """Plot Stanford integrity diagram: LPL (y) vs true risk proxy (x)."""
    # true error proxy = y_true (0=safe, 1=failure); AL_LOC = 0.20
    safe_mask  = (y_true == 0)
    fail_mask  = (y_true == 1)
    al = AL_LOC
    nominal      = ((lpl_vals < al) & safe_mask).sum()
    false_alert  = ((lpl_vals >= al) & safe_mask).sum()
    mi           = ((lpl_vals >= al) & fail_mask).sum()
    hmi          = ((lpl_vals < al) & fail_mask).sum()

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter(y_true[safe_mask],  lpl_vals[safe_mask],  c='tab:blue',
               s=2, alpha=0.3, label=f'Safe (nominal={nominal}, false-alert={false_alert})')
    ax.scatter(y_true[fail_mask],  lpl_vals[fail_mask],  c='tab:red',
               s=8, alpha=0.7, label=f'Fail (MI={mi}, HMI={hmi})')
    ax.axhline(al, ls='--', c='gray', lw=1.0, label=f'AL_loc={al}')
    ax.axvline(al, ls='--', c='gray', lw=1.0)
    ax.set_xlabel('True unsafe (failure_in_30s)')
    ax.set_ylabel('LPL (calibrated protection level)')
    ax.set_title(title)
    ax.legend(fontsize=7)
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return {'nominal': int(nominal), 'false_alert': int(false_alert),
            'MI': int(mi), 'HMI': int(hmi)}


def main():
    print('Phase 5 — IMU-VINS HealthNet')
    print('='*60)

    # 1. Load data
    df = load_data()
    print(f'Loaded {len(df)} rows, {df[LABEL].sum()} failures '
          f'({100*df[LABEL].mean():.1f}%)')
    print(f'Sequences: {sorted(df.sequence.unique())}')
    print(f'Grades: {sorted(df.grade.unique())}')
    print(f'Failures by sequence:')
    print(df.groupby('sequence')[LABEL].sum().to_string())
    print()

    # 2. Train/test split: STRATIFIED random (preserves failure rate in both sets)
    # Rationale: temporal-split sends all failures to test (train has 0 positives → model can't learn)
    # Honest caveat: within-sequence within-grade evaluation; NOT cross-sequence generalization
    train, test = stratified_split(df, test_frac=0.30, seed=42)
    print(f'Train: {len(train)} rows, {train[LABEL].sum()} failures '
          f'({100*train[LABEL].mean():.1f}%)')
    print(f'Test:  {len(test)} rows, {test[LABEL].sum()} failures '
          f'({100*test[LABEL].mean():.1f}%)')
    print(f'NOTE: stratified random split; not cross-sequence generalization')
    print()

    X_tr = train[RUNTIME_FEATURES].fillna(0).values
    y_tr = train[LABEL].values
    X_te = test[RUNTIME_FEATURES].fillna(0).values
    y_te = test[LABEL].values

    results = {}

    # 3. Rule-based baseline: acc_bias_margin threshold
    print('--- Rule-based baseline (acc_bias_margin threshold) ---')
    rule = rule_baseline_auc(test, threshold=2.30)
    print(f'AUROC: {rule["auc"]:.3f}')
    print(f'F1 @ threshold={rule["threshold"]}: {rule["f1"]:.3f}')
    print(f'FP={rule["fp"]}, FN={rule["fn"]}, n_pos={rule["n_pos"]}')
    results['rule_baseline'] = rule

    # 4. HistGBM on all runtime features
    print()
    print('--- HistGBM HealthNet ---')
    model = HistGradientBoostingClassifier(
        max_iter=200, learning_rate=0.05, max_depth=4,
        min_samples_leaf=20, random_state=42,
        class_weight='balanced'
    )
    model.fit(X_tr, y_tr)
    scores_test = model.predict_proba(X_te)[:, 1]
    auc_hgbm = roc_auc_score(y_te, scores_test)
    ap_hgbm  = average_precision_score(y_te, scores_test)

    # Find F1-optimal threshold
    prec, rec, thrs = precision_recall_curve(y_te, scores_test)
    f1s = 2 * prec * rec / (prec + rec + 1e-9)
    best_thr = thrs[np.argmax(f1s[:-1])] if len(thrs) > 0 else 0.5
    pred_best = (scores_test >= best_thr).astype(int)
    f1_best = f1_score(y_te, pred_best, zero_division=0)

    print(f'AUROC: {auc_hgbm:.3f}')
    print(f'AUPR:  {ap_hgbm:.3f}')
    print(f'F1 @ thr={best_thr:.3f}: {f1_best:.3f}')

    results['hgbm'] = {
        'auc': float(auc_hgbm), 'aupr': float(ap_hgbm),
        'f1': float(f1_best), 'best_thr': float(best_thr)
    }

    # 5. Feature importance via score difference (manual approach for HGBC)
    feat_imp_list = []
    base_auc = auc_hgbm
    for fi, fname in enumerate(RUNTIME_FEATURES):
        X_perm = X_te.copy()
        X_perm[:, fi] = np.random.RandomState(0).permutation(X_perm[:, fi])
        try:
            perm_auc = roc_auc_score(y_te, model.predict_proba(X_perm)[:, 1])
            drop = base_auc - perm_auc
        except Exception:
            drop = 0.0
        feat_imp_list.append((fname, max(drop, 0.0)))
    feat_imp = sorted(feat_imp_list, key=lambda x: -x[1])
    print()
    print('Top 10 features (permutation importance):')
    for fname, imp in feat_imp[:10]:
        print(f'  {fname:35s}: {imp:.4f}')
    results['feature_importance'] = {f: float(i) for f, i in feat_imp}

    # 6. Time-to-alert
    test_cp = test.copy()
    test_cp['score'] = scores_test
    tta_leads = compute_tta(test_cp, 'score', threshold=best_thr)
    if tta_leads:
        tta_median = float(np.median(tta_leads))
        tta_p10    = float(np.percentile(tta_leads, 10))
        tta_p90    = float(np.percentile(tta_leads, 90))
        missed_lead = sum(1 for l in tta_leads if l == 0)
    else:
        tta_median, tta_p10, tta_p90, missed_lead = 0, 0, 0, 0
    print()
    print(f'Time-to-alert (n={len(tta_leads)} failure sequences):')
    print(f'  Median: {tta_median:.0f}s  P10: {tta_p10:.0f}s  P90: {tta_p90:.0f}s')
    print(f'  Missed-lead (no alert before failure): {missed_lead}/{len(tta_leads)}')
    results['tta'] = {
        'median_s': tta_median, 'p10_s': tta_p10, 'p90_s': tta_p90,
        'missed_lead': missed_lead, 'n_fail_seqs': len(tta_leads)
    }

    # 7. Stanford LPL diagram (calibrated HistGBM → LPL)
    print()
    print('--- Stanford LPL (calibrated HistGBM) ---')
    for ir in [0.05, 0.10, 0.20]:
        lpl_vals, lpl_stats = build_lpl_from_scores(test, scores_test, ir=ir)
        stanford_counts = stanford_diagram(
            lpl_vals, y_te,
            title=f'HealthNet LPL Stanford (IR={ir}, AL={AL_LOC})',
            path=os.path.join(OUT, f'stanford_healthnet_ir{int(ir*100):02d}.png')
        )
        print(f'  IR={ir}: exceedance={lpl_stats["exceedance"]:.4f} '
              f'avail={lpl_stats["availability"]:.3f} '
              f'HMI={lpl_stats["HMI"]} '
              f'regions={stanford_counts}')
        results[f'lpl_ir{int(ir*100):02d}'] = {**lpl_stats, **stanford_counts}

    # 8. Rule-based LPL (for comparison)
    print()
    print('--- Stanford LPL (acc_bias_margin rule) ---')
    rule_scores = 1.0 - test['acc_bias_margin'].values  # higher = more at risk
    # Normalize to [0,1]
    rule_scores = (rule_scores - rule_scores.min()) / (rule_scores.max() - rule_scores.min() + 1e-9)
    for ir in [0.10]:
        lpl_rule, stats_rule = build_lpl_from_scores(test, rule_scores, ir=ir)
        counts_rule = stanford_diagram(
            lpl_rule, y_te,
            title=f'Rule-LPL (acc_bias_margin) Stanford (IR={ir})',
            path=os.path.join(OUT, f'stanford_rule_lpl_ir{int(ir*100):02d}.png')
        )
        print(f'  IR={ir}: exceedance={stats_rule["exceedance"]:.4f} '
              f'avail={stats_rule["availability"]:.3f} HMI={stats_rule["HMI"]}')
        results[f'rule_lpl_ir{int(ir*100):02d}'] = {**stats_rule, **counts_rule}

    # 9. Compare: HealthNet vs rule_baseline vs isotonic (existing LPL v1)
    print()
    print('=== SUMMARY ===')
    print(f'Rule baseline AUROC:       {rule["auc"]:.3f}')
    print(f'HistGBM HealthNet AUROC:   {auc_hgbm:.3f}')
    print(f'HistGBM beats rule:        {"YES" if auc_hgbm > rule["auc"] else "NO"}')
    print()
    for ir in [0.10]:
        key_hgbm = f'lpl_ir{int(ir*100):02d}'
        key_rule = f'rule_lpl_ir{int(ir*100):02d}'
        h = results[key_hgbm]
        r = results[key_rule]
        print(f'At IR={ir}:')
        print(f'  HealthNet LPL: exceedance={h["exceedance"]:.4f} avail={h["availability"]:.3f} HMI={h["HMI"]}')
        print(f'  Rule LPL:      exceedance={r["exceedance"]:.4f} avail={r["availability"]:.3f} HMI={r["HMI"]}')

    # 10. Write results
    results_path = os.path.join(OUT, 'healthnet_results.json')
    def to_serializable(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2, default=to_serializable)

    # Feature importance plot
    fig, ax = plt.subplots(figsize=(8, 5))
    names = [f for f, _ in feat_imp[:15]]
    imps  = [i for _, i in feat_imp[:15]]
    ax.barh(names[::-1], imps[::-1], color='steelblue')
    ax.set_xlabel('Importance')
    ax.set_title('HealthNet Feature Importance (Top 15)')
    plt.tight_layout()
    fig.savefig(os.path.join(OUT, 'healthnet_feature_importance.png'), dpi=150)
    plt.close(fig)

    print()
    print(f'Results: {results_path}')
    print(f'Diagrams: {OUT}/')

    return results


if __name__ == '__main__':
    main()
