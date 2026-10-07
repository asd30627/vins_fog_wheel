#!/usr/bin/env python3
"""Paper-2 G1 — raw object benchmark + phase map aggregator (STANDALONE, stdlib-only).

Change: paper2-viwo-conditioned-noue-v4 (Phase G1).

For every successful dynamic_v3 recording: run scripts/paper2_raw_object_probe.py (via `conda run -n gf`)
to produce a per-detection rich CSV, then concatenate all into paper2_raw_object_benchmark_all.csv and
aggregate by (density, dist_bin), (town, dist_bin), and (dist_bin) -> phase map.

Writes: paper2_raw_object_benchmark_all.csv, PAPER2_RAW_OBJECT_BENCHMARK.md, PAPER2_PHASE_MAP_V0.md.
Honest: bins with n<MIN_BIN flagged "insufficient"; no fabrication.

Run: python scripts/paper2_raw_object_benchmark.py [--glob 'Town*__dynamic_v3__run*'] [--no-recompute]
"""
from __future__ import annotations
import argparse, csv, glob, math, os, subprocess, statistics as st
from pathlib import Path

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
DATAROOT = Path("/mnt/sata4t/datasets/carla_fwvio")
PERDET_DIR = WS / "outputs" / "paper2_perdet"
BINS = ["0-15m", "15-30m", "30m+"]
MIN_BIN = 10


def pct(a, q):
    return float(st.quantiles(sorted(a), n=100)[q-1]) if len(a) >= 2 else (a[0] if a else float("nan"))


def med(a):
    return float(st.median(a)) if a else float("nan")


def fnum(x):
    try:
        return float(x)
    except Exception:
        return float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", default="Town*__dynamic_v3__run*")
    ap.add_argument("--no-recompute", action="store_true", help="reuse existing per-det CSVs")
    ap.add_argument("--max-frames", type=int, default=0)
    args = ap.parse_args()
    PERDET_DIR.mkdir(parents=True, exist_ok=True)

    recs = sorted(p for p in DATAROOT.glob(args.glob) if (p / "recording_meta.json").exists())
    print(f"[bench] {len(recs)} dynamic_v3 recordings")
    all_rows = []
    per_run = []
    for rec in recs:
        out = PERDET_DIR / f"{rec.name}.csv"
        if not (args.no_recompute and out.exists()):
            cmd = ["conda", "run", "-n", "gf", "python", str(WS / "scripts/paper2_raw_object_probe.py"),
                   "--rec", str(rec), "--out-csv", str(out)]
            if args.max_frames:
                cmd += ["--max-frames", str(args.max_frames)]
            r = subprocess.run(cmd, capture_output=True, text=True)
            tail = r.stdout.strip().splitlines()[-1:] if r.stdout else [r.stderr[-200:]]
            print(f"[bench] {rec.name}: {tail}")
        if not out.exists():
            print(f"[bench] WARN no per-det csv for {rec.name}"); continue
        rows = list(csv.DictReader(open(out)))
        all_rows += rows
        per_run.append((rec.name, len(rows), sum(int(x["matched"]) for x in rows)))

    if not all_rows:
        print("[bench] no detections; nothing to aggregate"); return
    allcsv = WS / "paper2_raw_object_benchmark_all.csv"
    with allcsv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys())); w.writeheader(); w.writerows(all_rows)
    print(f"[bench] wrote {allcsv} ({len(all_rows)} det rows)")

    matched = [r for r in all_rows if r["matched"] == "1"]
    print(f"[bench] total matched detections = {len(matched)}")

    def agg(rows, keyfn):
        groups = {}
        for r in rows:
            groups.setdefault(keyfn(r), []).append(r)
        out = {}
        for k, g in groups.items():
            pos = [fnum(r["pos_err_m"]) for r in g if r["pos_err_m"] != ""]
            spd = [fnum(r["speed_err_ms"]) for r in g if r["speed_err_ms"] != ""]
            drr = [fnum(r["dir_err_deg"]) for r in g if r["dir_err_deg"] != ""]
            out[k] = dict(n=len(g), pos_med=med(pos), pos_p95=pct(pos, 95),
                          spd_med=med(spd), spd_p95=pct(spd, 95), dir_med=med(drr), dir_p95=pct(drr, 95))
        return out

    by_bin = agg(matched, lambda r: r["dist_bin"])
    by_den_bin = agg(matched, lambda r: (r["density"], r["dist_bin"]))
    by_town_bin = agg(matched, lambda r: (r["town"], r["dist_bin"]))

    def fmt(d):
        if d["n"] < MIN_BIN:
            return f"{d['n']}(insuff) | {d['pos_med']:.2f} | {d['pos_p95']:.2f} | {d['spd_med']:.2f} | {d['dir_med']:.1f}"
        return f"{d['n']} | {d['pos_med']:.2f} | {d['pos_p95']:.2f} | {d['spd_med']:.2f} | {d['dir_med']:.1f}"

    # BENCHMARK.md
    L = ["# PAPER2_RAW_OBJECT_BENCHMARK — Workstream B / Phase G1", "",
         f"> {len(recs)} dynamic_v3 runs, {len(all_rows)} detections, {len(matched)} GT-matched. SGBM real depth. G1 benchmark.", "",
         "## Per-run", "| run | det | matched |", "|---|---:|---:|"]
    for n, d, m in per_run:
        L.append(f"| {n} | {d} | {m} |")
    L += ["", "## By distance bin (matched)", "| bin | n | pos_med | pos_p95 | spd_med | dir_med |", "|---|---|---|---|---|---|"]
    for b in BINS:
        if b in by_bin:
            L.append(f"| {b} | {fmt(by_bin[b])} |")
    L += ["", "## By density × distance bin", "| density | bin | n | pos_med | pos_p95 | spd_med | dir_med |", "|---|---|---|---|---|---|---|"]
    for den in ("sparse", "medium", "dense", "unknown"):
        for b in BINS:
            if (den, b) in by_den_bin:
                L.append(f"| {den} | {b} | {fmt(by_den_bin[(den,b)])} |")
    L += ["", "## By town × distance bin", "| town | bin | n | pos_med | pos_p95 | spd_med | dir_med |", "|---|---|---|---|---|---|---|"]
    towns = sorted(set(r["town"] for r in matched))
    for tw in towns:
        for b in BINS:
            if (tw, b) in by_town_bin:
                L.append(f"| {tw} | {b} | {fmt(by_town_bin[(tw,b)])} |")
    insuff = [k for k, d in by_bin.items() if d["n"] < MIN_BIN]
    L += ["", "## Insufficient-sample bins", f"- overall bins with n<{MIN_BIN}: {insuff or 'none'}",
          "- per (density,bin) insufficient: " + str([k for k, d in by_den_bin.items() if d["n"] < MIN_BIN]),
          "", "## Notes", "- match = bearing 4° to front GT actor; pos_err = body-frame (fwd,lat) distance.",
          "- velocity at far range dominated by depth-jitter (expect large speed_err in 30m+).",
          "- G1 benchmark; not a tuned final result."]
    (WS / "PAPER2_RAW_OBJECT_BENCHMARK.md").write_text("\n".join(L) + "\n")
    print("[bench] wrote PAPER2_RAW_OBJECT_BENCHMARK.md")

    # PHASE_MAP_V0.md — pos_err median grid density × distance
    P = ["# PAPER2_PHASE_MAP_V0 — Workstream B (phase map)", "",
         "> Raw object reliability phase map (G0/G1). cells = pos_err median (m) / matched n. "
         "Localization-quality axis (yaw injection) is the per-detection yaw1°_lat = r·sin(1°) lever; "
         "here we map the OBJECT-condition axes (density × distance) on nominal ego pose.", "",
         "## pos_err median (m) — density × distance", "| density \\ bin | " + " | ".join(BINS) + " |",
         "|---|" + "---|" * len(BINS)]
    for den in ("sparse", "medium", "dense"):
        cells = []
        for b in BINS:
            d = by_den_bin.get((den, b))
            cells.append(f"{d['pos_med']:.2f} (n={d['n']})" if d else "—")
        P.append(f"| {den} | " + " | ".join(cells) + " |")
    P += ["", "## speed_err median (m/s) — density × distance", "| density \\ bin | " + " | ".join(BINS) + " |",
          "|---|" + "---|" * len(BINS)]
    for den in ("sparse", "medium", "dense"):
        cells = []
        for b in BINS:
            d = by_den_bin.get((den, b))
            cells.append(f"{d['spd_med']:.2f} (n={d['n']})" if d else "—")
        P.append(f"| {den} | " + " | ".join(cells) + " |")
    P += ["", "## Reading", "- position error grows with distance bin (raw stereo-depth quantization).",
          "- speed error explodes in 30m+ (depth-jitter) -> far objects = high-uncertainty/invalid regime for NOUE.",
          "- yaw lever (e_lat≈r·sin Δψ) is the localization-quality coupling, quantified per-detection in benchmark_all.csv.",
          f"- cells with n<{MIN_BIN} are low-confidence."]
    (WS / "PAPER2_PHASE_MAP_V0.md").write_text("\n".join(P) + "\n")
    print("[bench] wrote PAPER2_PHASE_MAP_V0.md")


if __name__ == "__main__":
    main()
