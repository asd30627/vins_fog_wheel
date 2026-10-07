"""Summarize T5-batch-v2 closed-loop results (post-rebuild, valid episodes only)."""
import glob, os, csv, json, statistics

LOG_DIR = os.path.expanduser('~/fwvio_estimator_ws_wheel/logs/closed_loop')
OUT_MD  = os.path.join(LOG_DIR, 'T5_BATCH_RESULTS.md')
STALE   = os.path.join(LOG_DIR, 'stale_prerebuild')

def load_csvs(pattern):
    rows = []
    for path in sorted(glob.glob(os.path.join(LOG_DIR, pattern))):
        if 'stale' in path:
            continue
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                row['_file'] = os.path.basename(path)
                rows.append(row)
    return rows

def flt(row, key, default=0.0):
    try: return float(row[key])
    except: return default

def mean(vals):
    return statistics.mean(vals) if vals else float('nan')

def pct(num, den):
    return 100.0 * num / den if den else float('nan')

rows = load_csvs('ep*.csv')
n = len(rows)

# Group by condition
groups = {}
for r in rows:
    pol = r['policy']
    fname = r['_file']
    if 'static' in fname:
        cond = f'{pol}_static'
    elif 'moving' in fname:
        cond = f'{pol}_moving'
    else:
        cond = pol
    groups.setdefault(cond, []).append(r)

CONDITIONS = ['baseline_static', 'baseline_moving', 'supervised_static', 'supervised_moving']

def stats(g):
    n = len(g)
    success = sum(1 for r in g if flt(r,'success') == 1)
    path    = [flt(r,'path_length_m') for r in g]
    freeze  = sum(1 for r in g if flt(r,'freezing') == 1)
    ft      = [flt(r,'freeze_time_s') for r in g]
    col     = sum(1 for r in g if flt(r,'collisions') > 0)
    nc      = sum(1 for r in g if flt(r,'near_collisions') > 0)
    hs      = sum(1 for r in g if flt(r,'hard_stop_final') == 1)
    fs      = sum(1 for r in g if flt(r,'false_safe') == 1)
    uns     = sum(1 for r in g if flt(r,'unnecessary_stop') == 1)
    return {
        'n': n,
        'success_n': success,
        'success_pct': pct(success, n),
        'path_mean': mean(path),
        'path_min': min(path) if path else float('nan'),
        'path_max': max(path) if path else float('nan'),
        'freeze_n': freeze,
        'freeze_pct': pct(freeze, n),
        'freeze_time_mean': mean(ft),
        'collisions_n': col,
        'near_collisions_n': nc,
        'hard_stop_n': hs,
        'false_safe_n': fs,
        'unnecessary_stop_n': uns,
    }

all_stats = {c: stats(groups.get(c, [])) for c in CONDITIONS}

lines = [
    "# T5-batch-v2 Closed-Loop Results (post-rebuild)",
    "",
    "**Build status:** `paper2_validity_bridge` rebuilt 2026-07-02; installed binary has `if self.honor_hard_stop and self.hard_stop:` (correct gate).",
    "**Pre-rebuild stale CSVs:** archived to `logs/closed_loop/stale_prerebuild/` (NOT used here).",
    "**Note:** `goal_sent=0` in all episodes is EXPECTED — builtin-controller mode does not use Nav2 goal actions.",
    "",
    f"**Total valid episodes:** {n}/20",
    "",
    "## Summary Table",
    "",
    "| Condition | n | Success% | Path mean (m) | Freeze% | Freeze time (s) | Collisions | Near-collisions | Hard-stop% | False-safe | Unnecessary-stop% |",
    "|---|---|---|---|---|---|---|---|---|---|---|",
]
for c in CONDITIONS:
    s = all_stats[c]
    if s['n'] == 0:
        lines.append(f"| {c} | 0 | — | — | — | — | — | — | — | — | — |")
        continue
    lines.append(
        f"| {c} | {s['n']} "
        f"| {s['success_pct']:.0f}% "
        f"| {s['path_mean']:.2f} "
        f"| {s['freeze_pct']:.0f}% "
        f"| {s['freeze_time_mean']:.1f} "
        f"| {s['collisions_n']} "
        f"| {s['near_collisions_n']} "
        f"| {pct(s['hard_stop_n'], s['n']):.0f}% "
        f"| {s['false_safe_n']} "
        f"| {pct(s['unnecessary_stop_n'], s['n']):.0f}% |"
    )

# Key comparisons
bl = {**all_stats.get('baseline_static', {}), **{'n2': all_stats.get('baseline_moving',{}).get('n',0)}}
bs = all_stats.get('baseline_static', {})
bm = all_stats.get('baseline_moving', {})
ss = all_stats.get('supervised_static', {})
sm = all_stats.get('supervised_moving', {})

lines += [
    "",
    "## Behavioral Verification",
    "",
    "### Baseline (honor_hard_stop=False) — should navigate freely despite hard_stop",
]
for c, s in [('baseline_static', bs), ('baseline_moving', bm)]:
    if s.get('n',0) == 0: continue
    verdict = "✓ CORRECT" if s['freeze_pct'] == 0 and s['success_pct'] == 100 else "✗ UNEXPECTED"
    lines.append(f"- **{c}:** success={s['success_pct']:.0f}%, path={s['path_mean']:.2f}m, freeze={s['freeze_pct']:.0f}% — {verdict}")

lines += [
    "",
    "### Supervised (honor_hard_stop=True) — should freeze when adapter fires hard_stop",
]
for c, s in [('supervised_static', ss), ('supervised_moving', sm)]:
    if s.get('n',0) == 0: continue
    verdict = "✓ CORRECT" if s['freeze_pct'] == 100 and s['success_pct'] == 0 else "✗ UNEXPECTED"
    lines.append(f"- **{c}:** success={s['success_pct']:.0f}%, path={s['path_mean']:.2f}m, freeze={s['freeze_pct']:.0f}% — {verdict}")

lines += [
    "",
    "## Unnecessary-Stop Analysis (over-conservatism of supervisor)",
    "",
    "An 'unnecessary stop' occurs when the adapter fires hard_stop but the outcome would have been safe (no collision).",
    "This measures the false-alert rate of the obstacle OPL channel in the closed-loop setting.",
    "",
]
for c, s in all_stats.items():
    if s['n'] == 0: continue
    lines.append(f"- **{c}:** unnecessary_stop={s['unnecessary_stop_n']}/{s['n']} ({pct(s['unnecessary_stop_n'],s['n']):.0f}%)")

lines += [
    "",
    "## Integrity Gate Assessment",
    "",
    "The supervised mode demonstrates the closed-loop effect of the obstacle OPL channel:",
    "- Baseline (no integrity gate): navigates to goal, zero collisions, high path coverage",
    "- Supervised (integrity gate active): freezes 100% of time (all episodes stop at adapter hard_stop)",
    "",
    "**Current limitation:** The obstacle OPL is over-conservative in this world — the `deg` obstacles",
    "(x≈4.2, x≈7.3, y=0) are unobservable (djit≥0.55) so the adapter flags EVERY episode immediately.",
    "This means: supervised vs baseline shows the EFFECT of the gate, but cannot yet discriminate",
    "true dangerous vs safe situations without a better observable-world setup.",
    "",
    "**Next step (4.2):** Design episodes where some obstacles ARE dangerous (would cause collision in baseline)",
    "and some are safely passable — to measure collision reduction AND unnecessary-stop tradeoff separately.",
    "",
    "## Per-Episode Detail",
    "",
    "| file | policy | success | path_m | freeze | freeze_t | collisions | hard_stop | false_safe |",
    "|---|---|---|---|---|---|---|---|---|",
]
for r in rows:
    lines.append(
        f"| {r['_file']} | {r['policy']} | {r.get('success','')} "
        f"| {flt(r,'path_length_m'):.3f} | {r.get('freezing','')} "
        f"| {flt(r,'freeze_time_s'):.1f} | {r.get('collisions','')} "
        f"| {r.get('hard_stop_final','')} | {r.get('false_safe','')} |"
    )

lines += [
    "",
    "---",
    "Generated by `scripts/paper2_t5_batch_summary.py`",
]

os.makedirs(LOG_DIR, exist_ok=True)
with open(OUT_MD, 'w') as f:
    f.write('\n'.join(lines) + '\n')

print(f"Written: {OUT_MD}")
print(f"Total episodes processed: {n}")
for c in CONDITIONS:
    s = all_stats[c]
    if s['n'] > 0:
        print(f"  {c}: n={s['n']} success={s['success_pct']:.0f}% path={s['path_mean']:.2f}m freeze={s['freeze_pct']:.0f}%")
