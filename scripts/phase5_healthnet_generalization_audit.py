#!/usr/bin/env python3
"""Phase 5 — HealthNet GENERALIZATION AUDIT (claim-verification only, no new branch).

Purpose: concretely demonstrate the generalization boundary of the Phase 5 HealthNet,
rather than merely asserting it. Uses the SAME data + feature pipeline as
scripts/phase5_healthnet.py (reliability_dataset.tsv). NO new data, NO model tuning.

Evaluates three splits and reports AUROC + test-positive counts for each:
  1. STRATIFIED RANDOM (the original headline split) — for reference.
  2. LEAVE-ONE-SEQUENCE-OUT (LOSO) — train on all sequences except the held-out one,
     test on held-out. This is the honest cross-sequence generalization test.
  3. LEAVE-ONE-GRADE-OUT (within failing sequence) — train on 2 synthetic grades of
     the failing sequence (+ all others), test on the 3rd grade of the failing sequence.
     Tests whether the entropy signal transfers across degradation grades.

Output: logs/phase5/healthnet_generalization_audit.json
"""
import os, json
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

ROOT = '/home/ivlab3/fwvio_estimator_ws_wheel'
OUT = os.path.join(ROOT, 'logs', 'phase5')

RUNTIME_FEATURES = [
    'feat_mgr_mean', 'feat_mgr_last', 'feat_raw_mean',
    'outlier_ratio_mean', 'outlier_ratio_max', 'inlier_count_mean',
    'coverage8_mean', 'entropy8_mean', 'reproj_res_mean', 'avg_track_len_mean',
    'visual_gate_pass_rate', 'visual_alpha_mean',
    'yaw_disagree_mean', 'yaw_disagree_norm_mean', 'yaw_disagree_max',
    'ba_norm_mean', 'ba_norm_last', 'ba_norm_max', 'ba_norm_slope',
    'bg_norm_mean', 'bg_norm_last', 'bg_norm_max', 'bg_norm_slope',
    'solver_ms_mean', 'vel_norm_mean', 'delta_p_norm_mean',
    'acc_norm_mean', 'acc_norm_std', 'acc_norm_max',
    'gyr_norm_mean', 'gyr_norm_max', 'yaw_rate_mean', 'yaw_rate_std',
    'acc_bias_margin',
]
LABEL = 'failure_in_30s'


def load_data():
    df = pd.read_csv(os.path.join(ROOT, 'kaist_grade_scripts', 'reliability_dataset.tsv'), sep='\t')
    cols = ['dataset', 'sequence', 'grade', 'rep', 'tau'] + RUNTIME_FEATURES + [LABEL]
    df = df[cols].copy()
    df[RUNTIME_FEATURES] = df[RUNTIME_FEATURES].apply(pd.to_numeric, errors='coerce')
    df[LABEL] = df[LABEL].astype(int)
    df = df.dropna(subset=RUNTIME_FEATURES).reset_index(drop=True)
    return df


def fit_auc(tr, te):
    """Train HGBM on tr, return AUROC on te (or None if te has <1 pos or <1 neg)."""
    npos_te = int(te[LABEL].sum())
    nneg_te = int((te[LABEL] == 0).sum())
    npos_tr = int(tr[LABEL].sum())
    if npos_te == 0 or nneg_te == 0:
        return {'auc': None, 'reason': 'test set has no positives or no negatives',
                'npos_tr': npos_tr, 'npos_te': npos_te, 'n_te': len(te)}
    if npos_tr == 0:
        # Model never saw a failure -> cannot learn; report degenerate AUROC anyway
        clf = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05,
                                             min_samples_leaf=20, random_state=42)
        # single-class train is impossible; return explicit degenerate marker
        return {'auc': None, 'reason': 'train set has ZERO positives (cannot learn failure)',
                'npos_tr': 0, 'npos_te': npos_te, 'n_te': len(te)}
    clf = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05,
                                         min_samples_leaf=20, random_state=42)
    clf.fit(tr[RUNTIME_FEATURES], tr[LABEL])
    score = clf.predict_proba(te[RUNTIME_FEATURES])[:, 1]
    auc = roc_auc_score(te[LABEL], score)
    return {'auc': float(auc), 'reason': 'ok', 'npos_tr': npos_tr,
            'npos_te': npos_te, 'n_te': len(te)}


def main():
    df = load_data()
    res = {}

    # Provenance
    res['failures_by_sequence'] = df.groupby('sequence')[LABEL].sum().astype(int).to_dict()
    res['failures_by_grade'] = df.groupby('grade')[LABEL].sum().astype(int).to_dict()
    res['rows_total'] = len(df)
    res['failures_total'] = int(df[LABEL].sum())

    # 1. Stratified random (reference)
    tr, te = train_test_split(df, test_size=0.30, stratify=df[LABEL], random_state=42)
    res['stratified_random'] = fit_auc(tr, te)

    # 2. Leave-one-sequence-out
    loso = {}
    for seq in sorted(df.sequence.unique()):
        tr = df[df.sequence != seq]
        te = df[df.sequence == seq]
        loso[seq] = fit_auc(tr, te)
    res['leave_one_sequence_out'] = loso

    # 3. Leave-one-grade-out within the failing sequence(s)
    fail_seqs = [s for s, n in res['failures_by_sequence'].items() if n > 0]
    logo = {}
    for seq in fail_seqs:
        seq_grades = sorted(df[(df.sequence == seq) & (df[LABEL] == 1)].grade.unique())
        for g in seq_grades:
            # test = held-out grade of failing seq; train = everything else
            te = df[(df.sequence == seq) & (df.grade == g)]
            tr = df.drop(te.index)
            logo[f'{seq}::{g}'] = fit_auc(tr, te)
    res['leave_one_grade_out'] = logo

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'healthnet_generalization_audit.json'), 'w') as f:
        json.dump(res, f, indent=1)

    # Console summary
    print('=== HealthNet Generalization Audit ===')
    print(f'rows={res["rows_total"]}  failures={res["failures_total"]}')
    print(f'failures_by_sequence={res["failures_by_sequence"]}')
    print(f'failures_by_grade={res["failures_by_grade"]}')
    print(f'\n[1] stratified_random: {res["stratified_random"]}')
    print('\n[2] leave-one-sequence-out:')
    for s, r in loso.items():
        print(f'   {s}: {r}')
    print('\n[3] leave-one-grade-out (failing seq):')
    for k, r in logo.items():
        print(f'   {k}: {r}')


if __name__ == '__main__':
    main()
