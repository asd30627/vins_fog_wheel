#!/usr/bin/env python3
"""OPL repair (P5): add the missing CONFIDENCE-gate baseline for obstacle position integrity.

Mirrors scripts/paper2_obstacle_opl_stanford.py's distance-gate logic, but gates on detection
confidence (accept as 'reliable' if det_conf >= C*) instead of range. Reports availability + HMI
(accepted-but-actually-invalid, i.e. false-safe) at AL=3m, IR=0.10, so it sits alongside the
existing distance-gate and Mondrian-OPL numbers as a complete baseline set.

Range gate already exists (= the distance-gate baseline). Confidence was the only missing one.
Uses existing data only; no VINS, no new recordings.
"""
import numpy as np, pandas as pd, json, os

CSV = '/home/ivlab3/fwvio_estimator_ws_wheel/paper2/paper2_kitti_validity_dataset.csv'
AL, IR = 3.0, 0.10
OUT = '/home/ivlab3/fwvio_estimator_ws_wheel/logs/obstacle_opl/confidence_gate_result.json'


def gate_pick_high(conf_cal, err_cal, al, ir):
    """Largest-accepting confidence cutoff C* s.t. accepted-set exceedance <= ir.
       Accept if conf >= C* (high conf = reliable). Lower C* => accept more."""
    cand = np.unique(np.quantile(conf_cal, np.linspace(0.0, 0.95, 40)))
    best_C = 1.01  # accept nothing
    for C in cand:
        acc = conf_cal >= C
        if acc.sum() < 20:
            continue
        exc = (err_cal[acc] > al).mean()
        if exc <= ir and C < best_C:
            best_C = C
    return best_C


def eval_gate(accept_mask, err, al):
    n = len(err)
    avail = accept_mask.mean()
    # HMI = accepted but actually unsafe (err > al)  -> false-safe
    hmi = int(((accept_mask) & (err > al)).sum())
    exc = float((err[accept_mask] > al).mean()) if accept_mask.sum() else float('nan')
    return dict(availability=round(float(avail), 4), HMI=hmi,
                accepted=int(accept_mask.sum()), exceedance_in_accepted=round(exc, 4), n=n)


def main():
    df = pd.read_csv(CSV)
    df = df.dropna(subset=['det_conf', 'range_m', 'pos_err_m']).reset_index(drop=True)
    err = df['pos_err_m'].abs().values
    conf = df['det_conf'].values
    rng = df['range_m'].values

    # scene-held-out style: split calibration/test by scene to avoid leakage (mirror OPL protocol)
    scenes = sorted(df['seq'].unique())
    rs = np.random.RandomState(0)
    rs.shuffle(scenes)
    half = len(scenes) // 2
    cal_scenes = set(scenes[:half]); te_scenes = set(scenes[half:])
    cal = df['seq'].isin(cal_scenes).values
    te = df['seq'].isin(te_scenes).values

    res = {'AL': AL, 'IR': IR, 'n_total': len(df),
           'cal_scenes': len(cal_scenes), 'te_scenes': len(te_scenes)}

    # confidence gate
    Cstar = gate_pick_high(conf[cal], err[cal], AL, IR)
    conf_acc_te = conf[te] >= Cstar
    res['confidence_gate'] = dict(Cstar=round(float(Cstar), 4), **eval_gate(conf_acc_te, err[te], AL))

    # distance gate (recompute here on same split for apples-to-apples)
    def pick_low(x_cal, e_cal):
        cand = np.unique(np.quantile(x_cal, np.linspace(0.05, 1.0, 40)))
        best = 0.0
        for X in cand:
            acc = x_cal <= X
            if acc.sum() < 20:
                continue
            if (e_cal[acc] > AL).mean() <= IR and X > best:
                best = X
        return best
    Xstar = pick_low(rng[cal], err[cal])
    dist_acc_te = rng[te] <= Xstar
    res['distance_gate'] = dict(Xstar=round(float(Xstar), 2), **eval_gate(dist_acc_te, err[te], AL))

    # naive accept-all (context)
    res['accept_all'] = eval_gate(np.ones(te.sum(), bool), err[te], AL)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, 'w'), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
