#!/usr/bin/env python3
"""Phase 5 TTA evaluation — temporal holdout within urban38-pankyo.

For each (sequence=urban38-pankyo, grade) group:
  - Sort by tau (time)
  - Find first failure window index t_fail
  - Test: windows from t_fail - LEAD_WINDOWS to t_fail + LEAD_WINDOWS (centered on failure)
  - Train: all other sequences + non-test windows from urban38-pankyo

This preserves temporal ordering and allows computing TRUE time-to-alert.
"""
import os, json
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

ROOT = '/home/ivlab3/fwvio_estimator_ws_wheel'
OUT  = os.path.join(ROOT, 'logs', 'phase5')

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
WINDOW_SECS = 5   # each row = 5s window

# Holdout: 8 windows before first failure + 4 windows after = 60s pre-alert window
LEAD_WINDOWS = 8   # 8 × 5s = 40s lead window for test
POST_WINDOWS = 2


def load_data():
    df = pd.read_csv(os.path.join(ROOT, 'kaist_grade_scripts',
                                  'reliability_dataset.tsv'), sep='\t')
    cols = ['dataset', 'sequence', 'grade', 'rep', 'tau'] + RUNTIME_FEATURES + [LABEL]
    df = df[cols].copy()
    df[RUNTIME_FEATURES] = df[RUNTIME_FEATURES].apply(pd.to_numeric, errors='coerce')
    df[LABEL] = df[LABEL].astype(int)
    return df.dropna(subset=RUNTIME_FEATURES).reset_index(drop=True)


def main():
    print('Phase 5 TTA Evaluation — Temporal Holdout within urban38-pankyo')
    print('=' * 60)

    df = load_data()

    FAIL_SEQ = 'urban38-pankyo'
    FAIL_GRADES = ['general_imu', 'industrial_fog', 'precision_mems']

    all_tta = []
    all_results = []

    for grade in FAIL_GRADES:
        mask = (df.sequence == FAIL_SEQ) & (df.grade == grade)
        group = df[mask].sort_values('tau').reset_index(drop=True)

        # Find first failure window
        fail_idxs = group[group[LABEL] == 1].index.tolist()
        if not fail_idxs:
            print(f'  {grade}: no failures found, skip')
            continue
        t_fail = fail_idxs[0]

        # Holdout: LEAD_WINDOWS before failure + POST_WINDOWS after
        test_start = max(0, t_fail - LEAD_WINDOWS)
        test_end   = min(len(group), t_fail + POST_WINDOWS + 1)
        test_mask  = group.index.isin(range(test_start, test_end))
        grp_test   = group[test_mask].copy()
        grp_train  = group[~test_mask].copy()

        print(f'\n  {grade}:')
        print(f'    Total windows: {len(group)}, first failure at idx={t_fail} '
              f'(tau={group.loc[t_fail,"tau"]:.0f})')
        print(f'    Test window: idx [{test_start}, {test_end}) = {len(grp_test)} windows')
        print(f'    Test failures: {grp_test[LABEL].sum()}')

        # Training data: all other sequences + non-test urban38-pankyo rows
        other_seq = df[(df.sequence != FAIL_SEQ) |
                       ((df.sequence == FAIL_SEQ) & (df.grade != grade))].copy()
        train_df = pd.concat([other_seq, grp_train], ignore_index=True)
        train_df = train_df.dropna(subset=RUNTIME_FEATURES)

        print(f'    Train: {len(train_df)} rows, {train_df[LABEL].sum()} failures')

        if train_df[LABEL].sum() == 0:
            print(f'    SKIP: no failures in training (expected for kaist_real_005)')
            continue

        X_tr = train_df[RUNTIME_FEATURES].fillna(0).values
        y_tr = train_df[LABEL].values
        X_te = grp_test[RUNTIME_FEATURES].fillna(0).values
        y_te = grp_test[LABEL].values

        if y_te.sum() == 0:
            print(f'    SKIP: no failures in test window')
            continue

        # Train HistGBM
        model = HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.05, max_depth=4,
            min_samples_leaf=10, random_state=42, class_weight='balanced'
        )
        model.fit(X_tr, y_tr)
        scores = model.predict_proba(X_te)[:, 1]

        # AUROC on test window
        try:
            auc = roc_auc_score(y_te, scores)
        except Exception:
            auc = float('nan')
        print(f'    Test AUROC: {auc:.3f}')

        # TTA: find first window in test where score > threshold AND before first failure
        thr = 0.5
        fail_in_test = grp_test[grp_test[LABEL] == 1].index.tolist()
        if fail_in_test:
            # Relative position within test group
            rel_fail = grp_test.index.get_loc(fail_in_test[0])
            test_scores = list(scores)
            pre_alerts = [i for i in range(rel_fail) if test_scores[i] >= thr]
            if pre_alerts:
                lead_windows = rel_fail - pre_alerts[0]
                lead_s = lead_windows * WINDOW_SECS
            else:
                lead_s = 0  # missed lead
            print(f'    Time-to-alert: {lead_s}s (lead_windows={rel_fail - pre_alerts[0] if pre_alerts else 0})')
            all_tta.append({'grade': grade, 'lead_s': lead_s, 'auc': float(auc)})

        all_results.append({
            'grade': grade,
            'fail_idx': int(t_fail),
            'test_n': len(grp_test),
            'test_failures': int(grp_test[LABEL].sum()),
            'train_n': int(len(train_df)),
            'train_failures': int(train_df[LABEL].sum()),
            'auc': float(auc),
            'lead_s': lead_s if fail_in_test else None
        })

    print('\n=== TTA SUMMARY ===')
    if all_tta:
        leads = [r['lead_s'] for r in all_tta]
        print(f'N failure sequences evaluated: {len(all_tta)}')
        print(f'TTA Median: {np.median(leads):.0f}s')
        print(f'TTA Mean:   {np.mean(leads):.0f}s')
        print(f'TTA P10:    {np.percentile(leads, 10):.0f}s')
        print(f'TTA P90:    {np.percentile(leads, 90):.0f}s')
        print(f'Missed lead (TTA=0): {sum(1 for l in leads if l == 0)}/{len(leads)}')
        for r in all_tta:
            print(f'  {r["grade"]}: TTA={r["lead_s"]}s (AUROC={r["auc"]:.3f})')
    else:
        print('No failure sequences evaluated.')

    with open(os.path.join(OUT, 'healthnet_tta_results.json'), 'w') as f:
        json.dump({'all_results': all_results, 'tta_summary': all_tta}, f, indent=2)
    print(f'\nSaved: {OUT}/healthnet_tta_results.json')


if __name__ == '__main__':
    main()
