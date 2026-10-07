#!/usr/bin/env python3
"""Paper-2 R7 — Urban-candidate scenario search pipeline.

Phases (sequential, gated):
  1. Preview recording (CARLA required): 3 variants × 5 towns
  2. Preview audit (YOLO probe + quality metrics)
  3. Core recording (PASS_PREVIEW only)
  4. VINS baseline smoke ×2 (no CARLA needed)
  5. Vision sensitivity gate (VINS ×2 per variant, DET2)
  STOP — do not proceed to TCSV life gate automatically.

Usage:
  python3 scripts/paper2_r7_pipeline.py [--from-phase N] [--only-towns T1,T2] [--dry-run]
  --from-phase 1   start from recording previews (default)
  --from-phase 2   start from preview audit (recordings already done)
  --from-phase 3   start from core recording (previews audited)
  --from-phase 4   start from VINS smoke (cores recorded)
  --from-phase 5   start from vision sensitivity (VINS smoke done)
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time
from pathlib import Path
import numpy as np

# ── Paths ─────────────────────────────────────────────────────────────────────
WS      = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
FW      = Path("/home/ivlab3/fwvio_ws")
DS      = Path("/mnt/sata4t/datasets/carla_fwvio")
OUTROOT = Path("/mnt/sata4t/ivlab3_data/fwvio/results/paper2_vinsaware")
MASKDIR = Path("/mnt/sata4t/ivlab3_data/fwvio/results/paper2_masks")
PERDET  = WS / "outputs" / "paper2_perdet"
COLLECT = FW / "scripts/collect_carla_v2.py"
RUN_ONE = WS / "scripts/paper2_vins_run_one.sh"
METRICS = WS / "scripts/paper2_vins_metrics.py"
DET2    = WS / "src/VINS-Fusion-ROS2-jazzy/config/carla/carla_stereo_imu_640_R3_b05_gm_DET2.yaml"
GF_PY   = "/home/ivlab3/miniconda3/envs/gf/bin/python"
CARLA_PY = "/home/ivlab3/miniconda3/envs/carla/bin/python"

CONDITION = "dynamic_v3r7"
PREVIEW_FRAMES = 100
CORE_FRAMES    = 720

TOWNS = ["Town01", "Town02", "Town04", "Town05", "Town10HD"]

# Preview variants: (run_tag, extra_flags)
PREVIEW_VARIANTS = [
    ("medium_near_r7_preview", ["--npc", "12", "--npc-global", "30"]),
    ("dense_near_r7_preview",  ["--npc", "20", "--npc-global", "55"]),
    ("dense_slow_r7_preview",  ["--npc", "20", "--npc-global", "55", "--npc-target-speed-frac", "55"]),
]

BASE_R7_FLAGS = [
    "--imu-at-vehicle-center", "--baseline", "0.2",
    "--drive-mode", "gentle_turn", "--base-speed", "6.0",
    "--ego-spawn-scan",
    "--npc-near-band", "8,70", "--npc-on-route", "--npc-skip-ego-lane",
    "--npc-autopilot-delay", "--npc-min-dist", "8",
    "--skip-aux", "--image-width", "640", "--image-height", "480",
    "--ramp-throttle-max", "0.30", "--settle-sec", "2.0",
    "--static-sec", "3.0", "--ramp-sec", "5.0",
]

VISION_GRADES    = ["ideal_imu", "industrial_fog"]
VISION_VARIANTS  = ["baseline", "all_object_mask", "oracle_mask", "random_control"]
VISION_REPS      = 2

# Quality thresholds
PREVIEW_MIN_EGO_PATH   = 20.0   # m for 100 drive frames
PREVIEW_MIN_MATCHED50  = 30     # matched<50m per 100 drive frames
PREVIEW_MIN_DET_FRAME  = 0.5    # detections per frame
PREVIEW_MAX_FULLFRAME  = 0.10   # full-frame ratio (glued face)
CORE_MIN_EGO_PATH      = 100.0  # m for 720 drive frames
CORE_MIN_MATCHED50     = 200
VINS_MAX_REP_ATE_DIFF  = 0.03   # 3%

# ── Utility ───────────────────────────────────────────────────────────────────
def log(msg: str):
    print(f"[r7] {msg}", flush=True)

def sh(cmd: list | str, check=False, **kw):
    if isinstance(cmd, str):
        log(f"$ {cmd[:110]}")
        return subprocess.run(cmd, shell=True, check=check, **kw)
    log(f"$ {' '.join(str(c) for c in cmd)[:110]}")
    return subprocess.run(cmd, check=check, **kw)

def recpath(town: str, run: str) -> Path:
    # collect_carla_v2.py writes: {town}__{condition}__run{run}
    return DS / f"{town}__{CONDITION}__run{run}"

def probe_metrics(rec: Path) -> dict:
    """Run YOLO per-det probe and return quality metrics dict."""
    perdet_csv = PERDET / f"{rec.name}.csv"
    if not perdet_csv.exists():
        log(f"  running YOLO probe: {rec.name}")
        r = sh([GF_PY,
                str(WS / "scripts/paper2_raw_object_probe.py"),
                "--rec", str(rec), "--out-csv", str(perdet_csv)],
               capture_output=True, text=True)
        if r.returncode != 0:
            log(f"  WARN probe failed: {r.stderr[:200]}")
            return {}
    else:
        log(f"  perdet exists: {perdet_csv.name}")

    import pandas as pd
    try:
        df = pd.read_csv(perdet_csv, low_memory=False)
    except Exception as e:
        log(f"  WARN reading perdet: {e}"); return {}

    for c in ["u", "v", "bbox_w", "bbox_h", "frame", "gt_dist_m", "matched"]:
        if c in df: df[c] = pd.to_numeric(df[c], errors="coerce")

    n_frames = int(df["frame"].nunique()) if "frame" in df else 0
    n_det = len(df)
    det_per_frame = n_det / max(n_frames, 1)

    matched = df[df["matched"] == 1] if "matched" in df else df
    matched50 = matched[matched["gt_dist_m"] < 50] if "gt_dist_m" in matched else matched

    # Full-frame ratio from bbox area
    fullframe_count = 0
    if "bbox_w" in df and "bbox_h" in df:
        area = df["bbox_w"] * df["bbox_h"]
        fullframe_count = int((area > 640 * 480 * 0.5).sum())
    fullframe_ratio = fullframe_count / max(n_det, 1)

    return {
        "n_frames": n_frames,
        "n_det": n_det,
        "det_per_frame": round(det_per_frame, 3),
        "n_matched": len(matched),
        "n_matched50": len(matched50),
        "fullframe_count": fullframe_count,
        "fullframe_ratio": round(fullframe_ratio, 4),
        "perdet_csv": str(perdet_csv),
    }


def ego_path_from_rec(rec: Path) -> float:
    """Estimate ego path length from GT json files."""
    gt_files = sorted(rec.glob("gt/*.json"))
    if len(gt_files) < 2:
        return 0.0
    pts = []
    for f in gt_files:
        try:
            d = json.loads(f.read_text())
            e = d["ego_pose"]
            pts.append([e["x"], e["y"], e["z"]])
        except Exception:
            pass
    if len(pts) < 2:
        return 0.0
    arr = np.array(pts)
    return float(np.sum(np.linalg.norm(np.diff(arr, axis=0), axis=1)))


def classify_preview(metrics: dict, ego_path: float) -> str:
    if not metrics:
        return "FAIL_PREVIEW"
    if ego_path < PREVIEW_MIN_EGO_PATH:
        return "FAIL_PREVIEW"
    if metrics.get("fullframe_ratio", 1.0) > PREVIEW_MAX_FULLFRAME:
        return "FAIL_PREVIEW"
    if metrics.get("n_matched50", 0) < PREVIEW_MIN_MATCHED50:
        if metrics.get("det_per_frame", 0) < PREVIEW_MIN_DET_FRAME:
            return "FAIL_PREVIEW"
        return "LOW_YIELD_PREVIEW"
    return "PASS_PREVIEW"


def classify_core(metrics: dict, ego_path: float) -> str:
    if not metrics:
        return "INVALID_R7"
    if ego_path < CORE_MIN_EGO_PATH:
        return "INVALID_R7"
    if metrics.get("fullframe_ratio", 1.0) > PREVIEW_MAX_FULLFRAME:
        return "INVALID_R7"
    if metrics.get("n_matched50", 0) < CORE_MIN_MATCHED50:
        return "LOW_YIELD_R7"
    return "PASS_CORE_R7"


# ── State persistence ─────────────────────────────────────────────────────────
STATE_FILE = WS / "paper2/track_a/r7_pipeline_state.json"

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"previews": {}, "cores": {}, "vins_smoke": {}, "vision": {}}

def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ── Phase 1: Record previews ───────────────────────────────────────────────────
def phase1_previews(towns: list[str], dry_run: bool, state: dict):
    log("\n=== PHASE 1: Preview recording ===")
    rows = []
    for town in towns:
        for run_tag, extra in PREVIEW_VARIANTS:
            key = f"{town}__{run_tag}"
            rec = recpath(town, run_tag)
            if rec.exists():
                log(f"  [skip] {rec.name} exists")
                state["previews"].setdefault(key, {"status": "recorded", "rec": str(rec)})
                save_state(state)
                rows.append({"town": town, "run_tag": run_tag, "key": key, "rec": str(rec), "status": "recorded"})
                continue
            if dry_run:
                log(f"  [dry] would record: {rec.name}")
                continue
            log(f"  recording: {rec.name}")
            cmd = [CARLA_PY, str(COLLECT),
                   "--town", town,
                   "--condition", CONDITION,
                   "--run", run_tag,
                   "--frames", str(PREVIEW_FRAMES),
                   "--run-kind", "preview",
                   ] + BASE_R7_FLAGS + extra
            r = sh(cmd, capture_output=False)
            status = "recorded" if rec.exists() else "FAIL_RECORD"
            state["previews"][key] = {"status": status, "rec": str(rec)}
            save_state(state)
            rows.append({"town": town, "run_tag": run_tag, "key": key, "rec": str(rec), "status": status})
            if status == "FAIL_RECORD":
                log(f"  WARN recording failed: {rec.name}")
    return rows


# ── Phase 2: Preview audit ────────────────────────────────────────────────────
def phase2_audit(towns: list[str], dry_run: bool, state: dict) -> dict:
    log("\n=== PHASE 2: Preview audit ===")
    audit_rows = []
    best_per_town: dict[str, tuple[str, dict]] = {}  # town -> (run_tag, audit_row)

    for town in towns:
        best_score = -1
        best_row = None
        for run_tag, _ in PREVIEW_VARIANTS:
            key = f"{town}__{run_tag}"
            rec = recpath(town, run_tag)
            if not rec.exists():
                log(f"  [skip] {rec.name} not recorded")
                continue
            if dry_run:
                log(f"  [dry] would audit: {rec.name}")
                continue
            log(f"  auditing: {rec.name}")
            m = probe_metrics(rec)
            ego_path = ego_path_from_rec(rec)
            quality = classify_preview(m, ego_path)
            row = {"town": town, "run_tag": run_tag, "key": key,
                   "ego_path": round(ego_path, 1), "quality": quality, **m}
            audit_rows.append(row)
            state["previews"].setdefault(key, {})["quality"] = quality
            state["previews"][key]["ego_path"] = round(ego_path, 1)
            state["previews"][key]["metrics"] = m
            save_state(state)
            log(f"  {town}/{run_tag}: quality={quality} ego={ego_path:.1f}m "
                f"n_matched50={m.get('n_matched50',0)} det/f={m.get('det_per_frame',0):.2f}")
            # score = matched<50m (primary) + ego_path bonus
            score = m.get("n_matched50", 0) + (0.5 if quality == "PASS_PREVIEW" else 0)
            if quality in ("PASS_PREVIEW",) and score > best_score:
                best_score = score
                best_row = (run_tag, row)
        if best_row:
            best_per_town[town] = best_row
            log(f"  {town} -> best preview: {best_row[0]} (score={best_score:.1f})")
        else:
            log(f"  {town} -> NO PASS_PREVIEW")

    # Write preview audit CSV + MD
    _write_preview_audit(audit_rows)
    return best_per_town


def _write_preview_audit(rows: list[dict]):
    csv_path = WS / "paper2/track_a/paper2_r7_preview_audit.csv"
    header = "town,run_tag,quality,ego_path,n_frames,n_det,det_per_frame,n_matched,n_matched50,fullframe_ratio\n"
    with open(csv_path, "w") as f:
        f.write(header)
        for r in rows:
            f.write(",".join(str(r.get(k, "")) for k in
                             ["town","run_tag","quality","ego_path","n_frames","n_det",
                              "det_per_frame","n_matched","n_matched50","fullframe_ratio"]) + "\n")
    md_lines = ["# PAPER2 R7 — Preview Audit", "",
                "> PASS_PREVIEW criteria: ego_path>20m, matched<50m>30, det/f>0.5, fullframe<0.10",
                "",
                "| town | run_tag | quality | ego_path | n_matched50 | det/frame | fullframe |",
                "|---|---|---|---|---|---|---|"]
    for r in rows:
        md_lines.append(f"| {r.get('town','')} | {r.get('run_tag','')} | {r.get('quality','')} | "
                        f"{r.get('ego_path','')} | {r.get('n_matched50','')} | "
                        f"{r.get('det_per_frame','')} | {r.get('fullframe_ratio','')} |")
    (WS / "paper2/track_a/PAPER2_R7_PREVIEW_AUDIT.md").write_text("\n".join(md_lines))
    log(f"  preview audit written: {csv_path}")


# ── Phase 3: Core recording ───────────────────────────────────────────────────
def phase3_cores(best_per_town: dict, dry_run: bool, state: dict) -> list[tuple]:
    log("\n=== PHASE 3: Core recording (PASS_PREVIEW only) ===")
    cores = []
    for town, (best_run_tag, _) in best_per_town.items():
        # derive core run name from preview name
        core_run = best_run_tag.replace("_preview", "_core").replace("r7_preview", "r7_core")
        if "core" not in core_run:
            core_run = core_run + "_core"
        rec = recpath(town, core_run)
        if rec.exists():
            log(f"  [skip] {rec.name} exists")
            cores.append((town, core_run, rec))
            continue
        if dry_run:
            log(f"  [dry] would record core: {rec.name}")
            continue
        # get extra flags from preview variant
        extra = next((e for t, e in PREVIEW_VARIANTS if t == best_run_tag), [])
        log(f"  recording core: {rec.name}")
        cmd = [CARLA_PY, str(COLLECT),
               "--town", town,
               "--condition", CONDITION,
               "--run", core_run,
               "--frames", str(CORE_FRAMES),
               "--run-kind", "core",
               ] + BASE_R7_FLAGS + extra
        r = sh(cmd, capture_output=False)
        if rec.exists():
            cores.append((town, core_run, rec))
            state["cores"][f"{town}__{core_run}"] = {"status": "recorded", "rec": str(rec)}
        else:
            log(f"  WARN core recording failed: {rec.name}")
            state["cores"][f"{town}__{core_run}"] = {"status": "FAIL_RECORD"}
        save_state(state)

    # Audit cores
    core_manifest = []
    for town, core_run, rec in cores:
        m = probe_metrics(rec)
        ego_path = ego_path_from_rec(rec)
        quality = classify_core(m, ego_path)
        log(f"  core {town}/{core_run}: {quality} ego={ego_path:.1f}m matched50={m.get('n_matched50',0)}")
        core_manifest.append({"town": town, "run": core_run, "rec": str(rec),
                               "quality": quality, "ego_path": round(ego_path,1), **m})
        key = f"{town}__{core_run}"
        state["cores"].setdefault(key, {})["quality"] = quality
        state["cores"][key]["ego_path"] = round(ego_path, 1)
        state["cores"][key]["metrics"] = m
        save_state(state)

    _write_core_manifest(core_manifest)
    return [(r["town"], r["run"], Path(r["rec"])) for r in core_manifest if r["quality"] == "PASS_CORE_R7"]


def _write_core_manifest(rows: list[dict]):
    csv_path = WS / "paper2/track_a/paper2_r7_core_manifest.csv"
    header = "town,run,quality,ego_path,n_matched50,det_per_frame,fullframe_ratio\n"
    with open(csv_path, "w") as f:
        f.write(header)
        for r in rows:
            f.write(",".join(str(r.get(k,"")) for k in
                             ["town","run","quality","ego_path","n_matched50","det_per_frame","fullframe_ratio"]) + "\n")
    md = ["# PAPER2 R7 — Core Manifest", "",
          "| town | run | quality | ego_path | n_matched50 | det/frame | fullframe |",
          "|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r.get('town','')} | {r.get('run','')} | {r.get('quality','')} | "
                  f"{r.get('ego_path','')} | {r.get('n_matched50','')} | "
                  f"{r.get('det_per_frame','')} | {r.get('fullframe_ratio','')} |")
    (WS / "paper2/track_a/PAPER2_R7_CORE_MANIFEST.md").write_text("\n".join(md))
    log(f"  core manifest written: {csv_path}")


# ── Phase 4: VINS baseline smoke ──────────────────────────────────────────────
def phase4_vins_smoke(pass_cores: list, dry_run: bool, state: dict) -> list:
    log("\n=== PHASE 4: VINS baseline smoke (DET2, ideal_imu ×2) ===")
    vins_ready = []
    smoke_rows = []
    for town, core_run, rec in pass_cores:
        ates = []
        for rep in (1, 2):
            tag = f"r7_{town.lower()}_{core_run}_idealimu_r{rep}"
            outdir = OUTROOT / tag
            if (outdir / "vio.csv").exists():
                log(f"  [skip] {tag}")
            elif not dry_run:
                env = dict(os.environ)
                env["RC_CONFIG"] = str(DET2)
                env["REL_IMU_GRADE"] = "ideal_imu"
                log(f"  running VINS: {tag}")
                with open(outdir.parent / f"{tag}.drv.log", "w") as lf:
                    outdir.mkdir(parents=True, exist_ok=True)
                    subprocess.run(["bash", str(RUN_ONE), str(rec), tag, "0.5"],
                                   env=env, stdout=lf, stderr=subprocess.STDOUT)
            m = _get_metrics(rec, outdir, tag)
            ate = m.get("ate_rmse")
            ates.append(float(ate) if ate else float("nan"))
            smoke_rows.append({"town": town, "run": core_run, "rep": rep, "tag": tag,
                                "ate_rmse": ate, "n_vio": m.get("n_vio"),
                                "early": m.get("early_scale"), "late": m.get("late_scale"),
                                "fail": m.get("vins_failures"), "div": int(bool(m.get("diverged")))})
            log(f"  {tag}: ate={ate} n={m.get('n_vio')} early={m.get('early_scale')} late={m.get('late_scale')}")

        # classify
        valid = [a for a in ates if not np.isnan(a)]
        if len(valid) < 2:
            vins_class = "VINS_UNSTABLE_R7"
        elif max(valid) == 0:
            vins_class = "VINS_UNSTABLE_R7"
        elif abs(valid[0] - valid[1]) / max(valid) > VINS_MAX_REP_ATE_DIFF:
            vins_class = "NONDETERMINISTIC_R7"
        elif any(r["div"] for r in smoke_rows[-2:]):
            vins_class = "VINS_UNSTABLE_R7"
        else:
            vins_class = "VINS_READY_R7"
        log(f"  {town}/{core_run}: {vins_class} (ates={valid})")
        state["vins_smoke"][f"{town}__{core_run}"] = {"class": vins_class, "ates": valid}
        save_state(state)
        if vins_class == "VINS_READY_R7":
            vins_ready.append((town, core_run, rec))

    _write_vins_smoke(smoke_rows)
    return vins_ready


def _get_metrics(rec: Path, outdir: Path, tag: str) -> dict:
    r = subprocess.run([sys.executable, str(METRICS), str(rec), str(outdir), tag],
                       capture_output=True, text=True)
    for line in r.stdout.strip().splitlines():
        try:
            return json.loads(line)
        except Exception:
            pass
    return {}


def _write_vins_smoke(rows: list[dict]):
    csv_path = WS / "paper2/track_a/paper2_r7_vins_baseline_smoke.csv"
    header = "town,run,rep,tag,ate_rmse,n_vio,early,late,fail,div\n"
    with open(csv_path, "w") as f:
        f.write(header)
        for r in rows:
            f.write(",".join(str(r.get(k,"")) for k in
                             ["town","run","rep","tag","ate_rmse","n_vio","early","late","fail","div"]) + "\n")
    md = ["# PAPER2 R7 — VINS Baseline Smoke (DET2, ideal_imu)", "",
          "| town | run | rep | ATE | n_vio | early | late | class |",
          "|---|---|---|---|---|---|---|---|"]
    seen = set()
    for r in rows:
        key = f"{r['town']}__{r['run']}"
        cls = "see CSV"
        md.append(f"| {r['town']} | {r['run']} | {r['rep']} | {r.get('ate_rmse','')} | "
                  f"{r.get('n_vio','')} | {r.get('early','')} | {r.get('late','')} | {cls} |")
    (WS / "paper2/track_a/PAPER2_R7_VINS_BASELINE_SMOKE.md").write_text("\n".join(md))
    log(f"  VINS smoke written: {csv_path}")


# ── Phase 5: Vision sensitivity gate ──────────────────────────────────────────
def phase5_vision(vins_ready: list, dry_run: bool, state: dict):
    log("\n=== PHASE 5: Vision sensitivity gate ===")
    all_rows = []
    results: dict = {}

    for town, core_run, rec in vins_ready:
        # 1. Build masks
        mdir = MASKDIR / rec.name
        all_dyn = mdir / f"mask_{rec.name}__all_dynamic.json"
        oracle  = mdir / f"mask_{rec.name}__oracle.json"
        rand    = mdir / f"mask_{rec.name}__random_control.json"
        if not all_dyn.exists():
            perdet_csv = PERDET / f"{rec.name}.csv"
            if perdet_csv.exists():
                sh([sys.executable, str(WS/"scripts/paper2_make_vins_masks.py"),
                    "--run", rec.name, "--out-dir", str(mdir)], check=False)
        if not rand.exists() and all_dyn.exists():
            sh([sys.executable, str(WS/"scripts/paper2_make_random_mask.py"),
                "--all-dynamic", str(all_dyn), "--out", str(rand), "--seed", "7"], check=False)

        # 2. Run variants
        def _mask_path(variant: str) -> str | None:
            if variant == "baseline":        return None
            if variant == "all_object_mask": return str(all_dyn) if all_dyn.exists() else None
            if variant == "oracle_mask":     return str(oracle) if oracle.exists() else None
            if variant == "random_control":  return str(rand) if rand.exists() else None
            return None

        for grade in VISION_GRADES:
            for variant in VISION_VARIANTS:
                ates = []
                for rep in range(1, VISION_REPS + 1):
                    tag = f"r7vs_{town.lower()}_{core_run}_{grade}_{variant}_r{rep}"
                    outdir = OUTROOT / tag
                    if (outdir / "vio.csv").exists():
                        log(f"  [skip] {tag}")
                    elif not dry_run:
                        env = dict(os.environ)
                        env["RC_CONFIG"] = str(DET2)
                        env["REL_IMU_GRADE"] = grade
                        mp = _mask_path(variant)
                        if mp: env["MASK_JSON"] = mp
                        outdir.mkdir(parents=True, exist_ok=True)
                        with open(outdir.parent / f"{tag}.drv.log", "w") as lf:
                            subprocess.run(["bash", str(RUN_ONE), str(rec), tag, "0.5"],
                                           env=env, stdout=lf, stderr=subprocess.STDOUT)
                    m = _get_metrics(rec, outdir, tag)
                    ate = m.get("ate_rmse")
                    ates.append(float(ate) if ate else float("nan"))
                    all_rows.append({"town": town, "run": core_run, "grade": grade,
                                     "variant": variant, "rep": rep, "ate_rmse": ate,
                                     "n_vio": m.get("n_vio"), "diverged": int(bool(m.get("diverged"))),
                                     "tag": tag})
                    log(f"  {tag}: ate={ate}")

                valid = [a for a in ates if not np.isnan(a)]
                med = float(np.median(valid)) if valid else float("nan")
                results.setdefault((town, grade), {})[variant] = {"median_ate": med, "n": len(valid)}

    # Classify
    vision_class: dict = {}
    for (town, grade), variants in results.items():
        base_ate = variants.get("baseline", {}).get("median_ate", float("nan"))
        mask_ate = variants.get("all_object_mask", {}).get("median_ate", float("nan"))
        rand_ate = variants.get("random_control", {}).get("median_ate", float("nan"))
        if np.isnan(base_ate) or np.isnan(mask_ate):
            cls = "INSUFFICIENT_DATA"
        else:
            d_mask = (mask_ate - base_ate) / base_ate * 100 if base_ate > 0 else float("nan")
            d_rand = (rand_ate - base_ate) / base_ate * 100 if (base_ate > 0 and not np.isnan(rand_ate)) else float("nan")
            if d_mask < -5.0 and (np.isnan(d_rand) or d_rand > -3.0):
                cls = "VISION_ACTIVE"
            elif abs(d_mask) < 3.0:
                cls = "VISION_INERT"
            else:
                cls = "AMBIGUOUS"
        vision_class[(town, grade)] = cls
        log(f"  {town}/{grade}: {cls} (d_mask={d_mask:.1f}% d_rand={d_rand:.1f}%)" if not np.isnan(base_ate) else f"  {town}/{grade}: {cls}")

    _write_vision_results(all_rows, results, vision_class)
    state["vision"] = {f"{t}|{g}": c for (t, g), c in vision_class.items()}
    save_state(state)
    return vision_class


def _write_vision_results(rows: list, results: dict, vision_class: dict):
    csv_path = WS / "paper2/track_a/paper2_r7_vision_sensitivity_metrics.csv"
    header = "town,run,grade,variant,rep,ate_rmse,n_vio,diverged,tag\n"
    with open(csv_path, "w") as f:
        f.write(header)
        for r in rows:
            f.write(",".join(str(r.get(k,"")) for k in
                             ["town","run","grade","variant","rep","ate_rmse","n_vio","diverged","tag"]) + "\n")

    md = ["# PAPER2 R7 — Vision Sensitivity Results", "",
          "> VISION_ACTIVE: all_object/oracle reduces ATE ≥5% AND random_control < −3%", "",
          "## Classification", "",
          "| town | grade | d_mask% | d_rand% | verdict |",
          "|---|---|---|---|---|"]
    for (town, grade), cls in vision_class.items():
        v = results.get((town, grade), {})
        base = v.get("baseline", {}).get("median_ate", float("nan"))
        mask = v.get("all_object_mask", {}).get("median_ate", float("nan"))
        rand = v.get("random_control", {}).get("median_ate", float("nan"))
        dm = f"{(mask-base)/base*100:+.1f}%" if base > 0 and not np.isnan(mask) else "—"
        dr = f"{(rand-base)/base*100:+.1f}%" if base > 0 and not np.isnan(rand) else "—"
        md.append(f"| {town} | {grade} | {dm} | {dr} | **{cls}** |")
    (WS / "paper2/track_a/PAPER2_R7_VISION_SENSITIVITY_RESULTS.md").write_text("\n".join(md))
    log(f"  vision sensitivity written: {csv_path}")


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-phase", type=int, default=1)
    ap.add_argument("--only-towns", type=str, default="",
                    help="comma-separated town list, e.g. Town01,Town02")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    towns = TOWNS
    if a.only_towns:
        towns = [t.strip() for t in a.only_towns.split(",") if t.strip()]

    log(f"R7 pipeline: towns={towns} from_phase={a.from_phase} dry_run={a.dry_run}")
    log(f"Condition: {CONDITION}")

    state = load_state()

    # Phase 1: previews
    if a.from_phase <= 1:
        phase1_previews(towns, a.dry_run, state)

    # Phase 2: preview audit
    if a.from_phase <= 2:
        best_per_town = phase2_audit(towns, a.dry_run, state)
    else:
        # Reconstruct best_per_town from state
        best_per_town = {}
        for key, v in state["previews"].items():
            if v.get("quality") == "PASS_PREVIEW":
                town, run_tag = key.split("__", 1)
                if town in towns:
                    best_per_town[town] = (run_tag, v)

    if not best_per_town and not a.dry_run:
        log("No PASS_PREVIEW towns — stopping.")
        return

    # Phase 3: core recording
    if a.from_phase <= 3:
        pass_cores = phase3_cores(best_per_town, a.dry_run, state)
    else:
        pass_cores = []
        for key, v in state["cores"].items():
            if v.get("quality") == "PASS_CORE_R7":
                town, run = key.split("__", 1)
                if town in towns:
                    pass_cores.append((town, run, recpath(town, run)))

    if not pass_cores and not a.dry_run:
        log("No PASS_CORE_R7 — stopping.")
        return

    # Phase 4: VINS smoke
    if a.from_phase <= 4:
        vins_ready = phase4_vins_smoke(pass_cores, a.dry_run, state)
    else:
        vins_ready = []
        for key, v in state["vins_smoke"].items():
            if v.get("class") == "VINS_READY_R7":
                town, run = key.split("__", 1)
                if town in towns:
                    vins_ready.append((town, run, recpath(town, run)))

    if not vins_ready and not a.dry_run:
        log("No VINS_READY_R7 — stopping.")
        return

    # Phase 5: vision sensitivity (STOP after this)
    if a.from_phase <= 5:
        vision_class = phase5_vision(vins_ready, a.dry_run, state)

    log("\n=== R7 PIPELINE COMPLETE ===")
    log("STOP — do not run TCSV life gate without explicit approval.")
    log(f"State: {STATE_FILE}")
    log(f"Next: review paper2/track_a/PAPER2_R7_VISION_SENSITIVITY_RESULTS.md")


if __name__ == "__main__":
    main()
