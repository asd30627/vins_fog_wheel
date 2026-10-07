#!/usr/bin/env python3
"""Investigate Bas.norm()>2.5 on CARLA: protective or too conservative?
CARLA ran with soft-failure ON -> runs CONTINUE after the trigger, so we can see if the system
recovered (false alarm) or diverged (protective). Per acc-bias run: trigger time, ba@trigger, ba_max,
did ba RECOVER below 2.5 after trigger, late/early scale ratio, verdict.
Reads reliability_features_vins.csv (ba_norm per keyframe) from each carla_vins result dir + town_scan early/late."""
import os, csv
import numpy as np

RES = "/mnt/sata4t/ivlab3_data/fwvio/results/carla_vins"
ROW = "/home/ivlab3/fwvio_estimator_ws_wheel/autonomous_results/town_scan_rows.tsv"
THR = 2.5

# acc-bias runs from town scan: (town, route, tag). Use the 300s-row early/late (full run).
def load_scan():
    out = {}
    with open(ROW) as f:
        for r in csv.DictReader(f, delimiter='\t'):
            if r['mechanism'] != 'acc-bias>2.5' or r['dur_s'] != '300':
                continue
            tag = f"ts_{r['town']}_{r['route']}"
            try: e, l = float(r['early']), float(r['late'])
            except ValueError: e, l = float('nan'), float('nan')
            out[(r['town'], r['route'])] = (tag, e, l, r['fail_at_s'])
    return out

def ba_series(tag):
    p = f"{RES}/{tag}/reliability_features_vins.csv"
    if not os.path.exists(p): return None, None
    import pandas as pd
    df = pd.read_csv(p)
    if 'ba_norm' not in df: return None, None
    return df['timestamp'].astype(float).values, df['ba_norm'].astype(float).values

print(f"{'town':10}{'route':6}{'trig_s':>8}{'ba@trig':>9}{'ba_max':>8}{'ba_end':>8}{'n>2.5/tot':>11}{'recov':>7}"
      f"{'early':>7}{'late':>9}{'L/E':>8}{'  VERDICT'}")
scan = load_scan()
for (town, route), (tag, early, late, fas) in sorted(scan.items()):
    ts, ba = ba_series(tag)
    if ts is None:
        print(f"{town:10}{route:6}  (no reliability csv for {tag})"); continue
    t0 = ts[0]; rel = ts - t0
    trig = np.where(ba > THR)[0]
    ba_max = float(np.nanmax(ba)); ba_end = float(ba[-1])
    n_above = int(np.sum(ba > THR)); n_tot = len(ba)
    if len(trig):
        ti = trig[0]; trig_t = rel[ti]; ba_trig = ba[ti]
        # did ba recover below THR after trigger (and stay a while)?
        after = ba[ti+1:]
        frac_below = float(np.mean(after < THR)) if len(after) else 0.0
        recovered = "yes" if frac_below > 0.5 else ("partial" if frac_below > 0.1 else "no")
    else:
        trig_t = float('nan'); ba_trig = float('nan'); recovered = "no-trig"
    ratio = late/early if (early and early==early and late==late) else float('nan')
    # verdict: late/early<1.5 AND system near scale 1 -> trigger was a FALSE ALARM (too conservative)
    if ratio == ratio and ratio < 1.5 and abs(late-1.0) < 0.25:
        verdict = "FALSE-ALARM (too conservative)"
    elif ratio == ratio and ratio < 1.5:
        verdict = "drift-but-bounded (borderline)"
    elif ratio == ratio:
        verdict = "PROTECTIVE (real divergence)"
    else:
        verdict = "?"
    print(f"{town:10}{route:6}{trig_t:>8.1f}{ba_trig:>9.2f}{ba_max:>8.2f}{ba_end:>8.2f}{f'{n_above}/{n_tot}':>11}{recovered:>7}"
          f"{early:>7.2f}{late:>9.2f}{ratio:>8.2f}  {verdict}")
