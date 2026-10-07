#!/usr/bin/env python3
"""Build the final CARLA town-scan diagnostic table from town_scan_rows.tsv.
Assigns route labels straight/mixed/turny by MEASURED yawspan rank (per town), then emits the
user-requested columns: town | route | dur_s | init_ok | completion% | ATE_m | fail_at_s | fail_mechanism.
Writes markdown to CARLA_TOWN_SCAN.md."""
import sys, csv
from collections import defaultdict

ROW = sys.argv[1] if len(sys.argv) > 1 else "/home/ivlab3/fwvio_estimator_ws_wheel/autonomous_results/town_scan_rows.tsv"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/home/ivlab3/fwvio_estimator_ws_wheel/CARLA_TOWN_SCAN.md"
TOWN_ORDER = ["Town01","Town02","Town05","Town06","Town07","Town10HD","Town11","Town12"]

rows = list(csv.DictReader(open(ROW), delimiter="\t"))
# turnfrac per (town, route_tag) — measured route excitation (% of distance turning >2deg/s)
yaw = {}
for r in rows:
    k = (r["town"], r["route"])
    try: v = float(r["turnfrac"])
    except (ValueError, TypeError): continue
    yaw[k] = max(yaw.get(k, -1), v)

# Route label = DESIGN descriptor (drive mode + spawn). Measured turn-fraction did NOT cleanly
# tri-partition into straight/mixed/turny (autopilot covers more distance -> higher cumulative turning
# than the slow gentle_turn routes), so design labels + a measured turnfrac% column are more honest.
DESIGN = {"rA": "gturn@0", "rB": "auto@0", "rC": "gturn@50"}
label = {}
for r in rows:
    label[(r["town"], r["route"])] = DESIGN.get(r["route"], r["route"])

def tnum(t):
    try: return TOWN_ORDER.index(t)
    except ValueError: return 99

L = ["# CARLA town divergence scan — diagnostic table\n",
     "> 8 towns x 3 routes x 3 durations. Recipe = established wheel-se2 sigma 0.001 + soft-failure (現況, no tuning).",
     "> route = DESIGN descriptor (gturn=gentle_turn, auto=autopilot, @N=spawn index). turnfrac% = measured % of",
     ">   drive-distance turning >2°/s (routes did NOT cleanly split straight/mixed/turny — see report).",
     "> rec_s = seconds CARLA could RECORD before the engine crashed (separate from VINS divergence).",
     "> dur_s row > rec_s -> CARLA_REC_CRASH (engine couldn't produce that long); VINS metrics only within recorded data.",
     "> Town08/Town09 EXCLUDED: do not exist in CARLA public release.\n",
     "| town | route | turnfrac% | rec_s | dur_s | init_ok | completion% | ATE_m | fail_at_s | fail_mechanism |",
     "|---|---|---|---|---|---|---|---|---|---|"]
def dur_key(r):
    try: return int(r["dur_s"])
    except: return 0
for r in sorted(rows, key=lambda r: (tnum(r["town"]), label.get((r["town"], r["route"]), r["route"]), dur_key(r))):
    lab = label.get((r["town"], r["route"]), r["route"])
    ys = yaw.get((r["town"], r["route"]), "-")
    ys_s = f"{ys:.0f}" if isinstance(ys, float) else "-"
    io = "yes" if r.get("init_ok") == "1" else ("no" if r.get("init_ok") in ("0","") else r.get("init_ok"))
    rs = r.get("rec_s", "-")
    L.append(f"| {r['town']} | {lab} | {ys_s} | {rs} | {r['dur_s']} | {io} | {r['completion']} | {r['ATE_m']} | {r['fail_at_s']} | {r['mechanism']} |")

# summary: per-town stable durations
L.append("\n## Summary — longest stable (init_ok & completion>90 & mechanism OK/scale-drift-but-bounded) per town×route")
byroute = defaultdict(dict)
for r in rows:
    byroute[(r["town"], label.get((r["town"], r["route"]), r["route"]))][r["dur_s"]] = r
L.append("| town | route | 30s | 120s | 300s |")
L.append("|---|---|---|---|---|")
def cell(r):
    if not r: return "-"
    ok = r.get("init_ok")=="1"
    return f"{r['mechanism']}({r['completion']}%)" if ok else f"{r['mechanism']}"
for (town, lab) in sorted(byroute, key=lambda x: (tnum(x[0]), x[1])):
    d = byroute[(town, lab)]
    L.append(f"| {town} | {lab} | {cell(d.get('30'))} | {cell(d.get('120'))} | {cell(d.get('300'))} |")

txt = "\n".join(L)
open(OUT, "w").write(txt)
print(txt)
print(f"\n[table -> {OUT}]")
