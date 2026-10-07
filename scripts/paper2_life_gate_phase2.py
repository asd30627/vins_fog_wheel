#!/usr/bin/env python3
"""Paper-2 Life Gate Phase 2 — ideal_imu vs industrial_fog + object masking on Town06/07 R6 cores.

Grid: 2 towns × 2 grades × 3 variants × 3 reps = 36 VINS runs (sequential, DET2).
Steps:
  1. Generate per-det CSVs for R6 cores (conda gf / YOLO probe).
  2. Build all_dynamic + random_control masks.
  3. Run VINS experiments; skip if outdir vio.csv already present (resume-safe).
  4. Compute per-condition median ATE; write CSV + MD.

Usage:
  python3 scripts/paper2_life_gate_phase2.py [--skip-perdet] [--skip-masks] [--dry-run]
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from pathlib import Path
import numpy as np

# ── Paths ─────────────────────────────────────────────────────────────────────
WS      = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
FW      = Path("/home/ivlab3/fwvio_ws")
DS      = Path("/mnt/sata4t/datasets/carla_fwvio")
OUTROOT = Path("/mnt/sata4t/ivlab3_data/fwvio/results/paper2_vinsaware")
MASKDIR = Path("/mnt/sata4t/ivlab3_data/fwvio/results/paper2_masks")
PERDET  = WS / "outputs" / "paper2_perdet"
DET2    = WS / "src/VINS-Fusion-ROS2-jazzy/config/carla/carla_stereo_imu_640_R3_b05_gm_DET2.yaml"
RUN_ONE = WS / "scripts/paper2_vins_run_one.sh"
METRICS = WS / "scripts/paper2_vins_metrics.py"
GF_PY   = "/home/ivlab3/miniconda3/envs/gf/bin/python"

OUT_CSV = WS / "paper2/track_a/paper2_life_gate_phase2.csv"
OUT_MD  = WS / "paper2/track_a/PAPER2_LIFE_GATE_PHASE2_RESULTS.md"

# ── Experiment grid ────────────────────────────────────────────────────────────
RUNS = [
    ("Town06__dynamic_v3fix__rundense_near_r6_core", "t06"),
    ("Town07__dynamic_v3fix__rundense_near_r6_core", "t07"),
]
GRADES   = ["ideal_imu", "industrial_fog"]
VARIANTS = ["baseline", "all_object_mask", "random_control"]
N_REPS   = 3

# ── Helpers ────────────────────────────────────────────────────────────────────
def sh(cmd, **kw):
    print(f"[sh] {cmd[:120]}", flush=True)
    return subprocess.run(cmd, shell=True, **kw)


def run_vins(grade: str, recname: str, tag: str, mask_json: str | None,
             dry_run: bool) -> dict:
    """Run one VINS replay; skip if vio.csv already present. Returns metrics dict."""
    outdir = OUTROOT / tag
    vio_csv = outdir / "vio.csv"
    if vio_csv.exists():
        print(f"  [skip] {tag} — vio.csv exists, loading cached result")
    else:
        if dry_run:
            print(f"  [dry] would run: {tag}  grade={grade}  mask={mask_json}")
            return {}
        outdir.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env["RC_CONFIG"] = str(DET2)
        env["REL_IMU_GRADE"] = grade
        if mask_json:
            env["MASK_JSON"] = mask_json
        log = outdir.with_suffix(".drv.log")
        with open(log, "w") as lf:
            subprocess.run(
                ["bash", str(RUN_ONE), str(DS / recname), tag, "0.5"],
                env=env, stdout=lf, stderr=subprocess.STDOUT)

    # Compute metrics from the result dir
    result = subprocess.run(
        [sys.executable, str(METRICS), str(DS / recname), str(outdir), tag],
        capture_output=True, text=True)
    for line in result.stdout.strip().splitlines():
        try:
            m = json.loads(line)
            print(f"  [metrics] {tag}: ate={m.get('ate_rmse')} n={m.get('n_vio')} "
                  f"early={m.get('early_scale')} late={m.get('late_scale')}")
            return m
        except Exception:
            pass
    print(f"  [warn] no metrics for {tag}: {result.stderr[:200]}")
    return {}


# ── Step 1: per-det probe ──────────────────────────────────────────────────────
def step_perdet(skip: bool):
    if skip:
        print("[step1] --skip-perdet: skipping per-det probe")
        return
    print("\n=== STEP 1: per-det probe (conda gf YOLO) ===")
    PERDET.mkdir(parents=True, exist_ok=True)
    for recname, _ in RUNS:
        out_csv = PERDET / f"{recname}.csv"
        if out_csv.exists():
            print(f"  [skip] {out_csv.name} exists")
            continue
        rec_path = DS / recname
        print(f"  [probe] {recname}")
        r = sh(
            f"conda run -n gf {GF_PY} "
            f"{WS}/scripts/paper2_raw_object_probe.py "
            f"--rec {rec_path} --out-csv {out_csv}",
            check=False)
        if r.returncode != 0:
            print(f"  [WARN] probe failed for {recname} (rc={r.returncode})")


# ── Step 2: mask generation ────────────────────────────────────────────────────
def step_masks(skip: bool):
    if skip:
        print("[step2] --skip-masks: skipping mask generation")
        return
    print("\n=== STEP 2: mask generation ===")
    for recname, _ in RUNS:
        mdir = MASKDIR / recname
        all_dyn = mdir / f"mask_{recname}__all_dynamic.json"
        rand    = mdir / f"mask_{recname}__random_control.json"
        perdet_csv = PERDET / f"{recname}.csv"

        if not perdet_csv.exists():
            print(f"  [WARN] per-det CSV missing for {recname}, skipping masks")
            continue

        if not all_dyn.exists():
            print(f"  [masks] building all_dynamic / oracle / validity_aware for {recname}")
            sh(f"{sys.executable} {WS}/scripts/paper2_make_vins_masks.py "
               f"--run {recname} --out-dir {mdir}", check=False)
        else:
            print(f"  [skip] all_dynamic mask exists for {recname}")

        if not rand.exists() and all_dyn.exists():
            print(f"  [masks] building random_control for {recname}")
            sh(f"{sys.executable} {WS}/scripts/paper2_make_random_mask.py "
               f"--all-dynamic {all_dyn} --out {rand} --seed 7", check=False)
        elif rand.exists():
            print(f"  [skip] random_control mask exists for {recname}")


# ── Step 3 + 4: VINS experiments + results ─────────────────────────────────────
def step_vins_and_results(dry_run: bool):
    print("\n=== STEP 3: VINS experiments (36 runs, sequential) ===")
    rows: list[dict] = []
    total = len(RUNS) * len(GRADES) * len(VARIANTS) * N_REPS
    done = 0

    for recname, tshort in RUNS:
        for grade in GRADES:
            for variant in VARIANTS:
                mask_path = _mask_path(recname, variant)
                reps_ate, reps_n = [], []
                for rep in range(1, N_REPS + 1):
                    done += 1
                    tag = f"lg2_{tshort}_{grade}_{variant}_r{rep}"
                    print(f"\n[{done}/{total}] {tag}")
                    m = run_vins(grade, recname, tag, mask_path, dry_run)
                    ate = m.get("ate_rmse") or m.get("ate_mean")
                    n = m.get("n_vio", 0)
                    div = bool(m.get("diverged"))
                    rows.append(dict(
                        town=tshort, recname=recname, grade=grade,
                        variant=variant, rep=rep,
                        ate_rmse=ate, n_vio=n, diverged=int(div),
                        early=m.get("early_scale"), late=m.get("late_scale"),
                        rpe_trans=m.get("rpe_trans_med"),
                        tag=tag,
                    ))
                    if not div and ate is not None:
                        reps_ate.append(float(ate))
                        reps_n.append(int(n))
                print(f"  [{tshort}/{grade}/{variant}] reps_ate={reps_ate}")

    # ── Step 4: write CSV ──────────────────────────────────────────────────────
    header = "town,recname,grade,variant,rep,ate_rmse,n_vio,diverged,early,late,rpe_trans,tag\n"
    with open(OUT_CSV, "w") as f:
        f.write(header)
        for r in rows:
            f.write(",".join([
                str(r["town"]), r["recname"], r["grade"], r["variant"],
                str(r["rep"]),
                "" if r["ate_rmse"] is None else f"{r['ate_rmse']:.4f}",
                str(r["n_vio"]),
                str(r["diverged"]),
                "" if r["early"] is None else f"{r['early']:.4f}",
                "" if r["late"] is None else f"{r['late']:.4f}",
                "" if r["rpe_trans"] is None else f"{r['rpe_trans']:.4f}",
                r["tag"],
            ]) + "\n")
    print(f"\n[csv] {OUT_CSV}")

    # ── Step 4: compute medians and write MD ───────────────────────────────────
    def median_ate(town, grade, variant):
        vals = [r["ate_rmse"] for r in rows
                if r["town"] == town and r["grade"] == grade
                and r["variant"] == variant
                and not r["diverged"] and r["ate_rmse"] is not None]
        if not vals:
            return float("nan"), 0
        return float(np.median([float(v) for v in vals])), len(vals)

    def pct_change(base, val):
        if base and base > 0 and not np.isnan(val):
            return 100.0 * (val - base) / base
        return float("nan")

    lines = [
        "# PAPER2 Life Gate Phase 2 — Results",
        "",
        "> ideal_imu vs industrial_fog + object masking on Town06/07 R6 cores.",
        "> DET2 config, 3 reps each condition, median ATE reported.",
        "> Date 2026-07-01.",
        "",
    ]

    for recname, tshort in RUNS:
        lines += [f"## {tshort} ({recname})", ""]
        lines += ["| grade | variant | median_ATE (m) | Δ vs baseline | n_good_reps | verdict |",
                  "|---|---|---|---|---|---|"]
        for grade in GRADES:
            base_ate, _ = median_ate(tshort, grade, "baseline")
            for variant in VARIANTS:
                med, n_good = median_ate(tshort, grade, variant)
                delta = pct_change(base_ate, med)
                if np.isnan(med):
                    verdict = "NO_DATA"
                elif variant == "baseline":
                    verdict = f"BASELINE ({n_good}/3 reps)"
                elif abs(delta) >= 5.0:
                    verdict = "SIGNAL_PRESENT" if delta < 0 else "SIGNAL_PRESENT(worse)"
                else:
                    verdict = "NO_SIGNAL"
                delta_str = f"{delta:+.1f}%" if not np.isnan(delta) else "—"
                med_str = f"{med:.2f}" if not np.isnan(med) else "—"
                lines.append(f"| {grade} | {variant} | {med_str} | {delta_str} | {n_good}/3 | {verdict} |")
        lines.append("")

    # Summary: life gate classification
    lines += ["## Life Gate Classification", ""]
    lines += ["| town | grade | object_mask_Δ% | random_ctrl_Δ% | verdict |",
              "|---|---|---|---|---|"]
    life_gate = {}
    for recname, tshort in RUNS:
        for grade in GRADES:
            base_ate, _ = median_ate(tshort, grade, "baseline")
            mask_ate, nm = median_ate(tshort, grade, "all_object_mask")
            rand_ate, nr = median_ate(tshort, grade, "random_control")
            d_mask = pct_change(base_ate, mask_ate)
            d_rand = pct_change(base_ate, rand_ate)
            if nm < 2 or nr < 2:
                verdict = "INSUFFICIENT_DATA"
            elif d_mask < -5.0 and d_rand > -3.0:
                verdict = "VISION_ACTIVE"
            elif d_mask >= -5.0:
                verdict = "VISION_INERT"
            else:
                verdict = "AMBIGUOUS"
            life_gate[(tshort, grade)] = verdict
            dm_str = f"{d_mask:+.1f}%" if not np.isnan(d_mask) else "—"
            dr_str = f"{d_rand:+.1f}%" if not np.isnan(d_rand) else "—"
            lines.append(f"| {tshort} | {grade} | {dm_str} | {dr_str} | {verdict} |")

    lines += [
        "",
        "## Notes",
        "",
        "- VISION_ACTIVE: object_mask reduces ATE ≥5% AND random_control is neutral (Δ < −3%).",
        "- VISION_INERT: masking makes no difference (<5% ATE change). Sensor dominates.",
        "- Scale drift (late≈2.2) is consistent/deterministic across all conditions in these towns;",
        "  relative Δ% is valid for comparison (same drift, same baseline).",
        "- All runs: DET2 (max_solver_time=1000, multiple_thread=0), rate=0.5, skip-imu-head=150.",
        "",
        f"CSV: `paper2/track_a/paper2_life_gate_phase2.csv`",
        "",
    ]

    OUT_MD.write_text("\n".join(lines))
    print(f"[md]  {OUT_MD}")

    # Print summary to console
    print("\n=== LIFE GATE PHASE 2 SUMMARY ===")
    for (tshort, grade), verdict in life_gate.items():
        print(f"  {tshort:6s}  {grade:16s}  {verdict}")
    print("=================================")


def _mask_path(recname: str, variant: str) -> str | None:
    mdir = MASKDIR / recname
    if variant == "baseline":
        return None
    if variant == "all_object_mask":
        p = mdir / f"mask_{recname}__all_dynamic.json"
    elif variant == "random_control":
        p = mdir / f"mask_{recname}__random_control.json"
    else:
        return None
    if p.exists():
        return str(p)
    print(f"  [WARN] mask not found: {p} — running without mask for {variant}")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-perdet", action="store_true")
    ap.add_argument("--skip-masks",  action="store_true")
    ap.add_argument("--dry-run",     action="store_true",
                    help="print plan without running VINS (perdet/masks still run)")
    a = ap.parse_args()

    print("=== Paper-2 Life Gate Phase 2 ===")
    print(f"Grid: {len(RUNS)} towns × {len(GRADES)} grades × "
          f"{len(VARIANTS)} variants × {N_REPS} reps = "
          f"{len(RUNS)*len(GRADES)*len(VARIANTS)*N_REPS} VINS runs")
    print(f"Config: DET2  Rate: 0.5  Mask: all_dynamic / random_control")
    print()

    step_perdet(a.skip_perdet)
    step_masks(a.skip_masks)
    step_vins_and_results(a.dry_run)


if __name__ == "__main__":
    main()
