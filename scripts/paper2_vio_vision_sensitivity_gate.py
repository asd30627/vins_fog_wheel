#!/usr/bin/env python3
"""Paper-2 life gate — VISION SENSITIVITY (does the vision channel influence VINS pose at each IMU grade?).

For each IMU gyro grade x run, run deterministic (DET2) VINS with vision perturbations (NO TCSV yet):
  baseline | baseline_rep (determinism) | feature_dropout_60 | backend_cull_off
and classify the SETTING as VISION_INERT / VISION_ACTIVE / UNSTABLE from how much the perturbations move
ATE/RPE relative to baseline. Only VISION_ACTIVE settings advance to the Phase-3 life gate.

Strictly SEQUENTIAL (one vins_node at a time — parallel => ROS node-name collision corrupts runs).
"""
from __future__ import annotations
import subprocess, json, sys, os, shutil
from pathlib import Path

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
FW = Path("/home/ivlab3/fwvio_ws")
DS = Path("/mnt/sata4t/datasets/carla_fwvio")
OUTROOT = Path("/mnt/sata4t/ivlab3_data/fwvio/results/paper2_vinsaware")
DET2 = WS / "src/VINS-Fusion-ROS2-jazzy/config/carla/carla_stereo_imu_640_R3_b05_gm_DET2.yaml"
RUN_ONE = WS / "scripts/paper2_vins_run_one.sh"
METRICS = WS / "scripts/paper2_vins_metrics.py"
CSV = WS / "paper2/track_a/paper2_vision_sensitivity_metrics.csv"

# precision_mems DIVERGES (documented UNSTABLE); feature-dropout CRASHES (starves tracking) — both
# excluded as core probes. Core grid = stable grades x non-starving perturbations.
GRADES = ["ideal_imu", "industrial_fog"]
RUNS = [("dense_b1", "Town01__dynamic_v3__rundense_b1"),
        ("medium_b1", "Town01__dynamic_v3__runmedium_b1")]
MASKDIR = Path("/mnt/sata4t/ivlab3_data/fwvio/results/paper2_masks")
# variant -> (extra env builder given recname). Mask variants suppress object bboxes in the LEFT image.
def mask_env(recname, kind):
    return {"MASK_JSON": str(MASKDIR / recname / f"mask_{recname}__{kind}.json")}
VARIANTS = {
    "baseline":         lambda rn: {},
    "cull_off":         lambda rn: {"REL_BACKEND_OUTLIER_CULL": "0"},
    "all_object_mask":  lambda rn: mask_env(rn, "all_dynamic"),
    "oracle_mask":      lambda rn: mask_env(rn, "oracle"),
}

ACTIVE_ATE_PCT = 5.0     # >=5% ATE move by a vision perturbation => vision has real leverage
ACTIVE_RPE_PCT = 5.0


def run_one(grade, recname, tag, extra_env):
    rec = DS / recname
    outdir = OUTROOT / tag
    outdir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["RC_CONFIG"] = str(DET2)
    env["REL_IMU_GRADE"] = grade
    env.update(extra_env)
    subprocess.run(["bash", str(RUN_ONE), str(rec), tag, "0.5"],
                   env=env, stdout=open(outdir.with_suffix(".drv.log"), "w"), stderr=subprocess.STDOUT)
    mj = subprocess.run([sys.executable, str(METRICS), str(rec), str(outdir), tag],
                        capture_output=True, text=True).stdout.strip().splitlines()
    m = {}
    if mj:
        try: m = json.loads(mj[-1])
        except Exception: m = {}
    # internals from vins.log
    vlog = outdir / "vins.log"
    orr = fmgr = None
    if vlog.exists():
        rr, mg = [], []
        for ln in vlog.read_text(errors="ignore").splitlines():
            if "ratio=" in ln:
                try: rr.append(float(ln.split("ratio=")[1].split()[0]))
                except Exception: pass
            if "mgr=" in ln:
                try: mg.append(int(ln.split("mgr=")[1].split()[0]))
                except Exception: pass
        if rr: orr = round(sum(rr) / len(rr), 4)
        if mg: fmgr = round(sum(mg) / len(mg), 1)
    return m, orr, fmgr, str(outdir)


def main():
    rows = []
    header = ("grade,run,variant,ate_rmse,ate_mean,rpe_trans,early,late,vins_fail,n_vio,"
              "mean_outlier_ratio,feat_mgr,diverged,det_ok,ate_delta_pct,rpe_delta_pct,outdir")
    CSV.write_text(header + "\n")
    classify = {}
    for grade in GRADES:
        for run, recname in RUNS:
            base_m = None; base_dir = None
            for variant, extra_fn in VARIANTS.items():
                extra = extra_fn(recname)
                tag = f"vs_{grade}_{run}_{variant}"
                m, orr, fmgr, outdir = run_one(grade, recname, tag, extra)
                if variant == "baseline":
                    base_m = m; base_dir = outdir
                    # determinism repeat
                    m2, _, _, d2 = run_one(grade, recname, f"{tag}_rep", extra)
                    det_ok = "1" if (Path(base_dir, "vio.csv").exists() and Path(d2, "vio.csv").exists()
                                     and Path(base_dir, "vio.csv").read_bytes() == Path(d2, "vio.csv").read_bytes()) else "0"
                else:
                    det_ok = ""
                def pct(cur, base):
                    if cur is None or base in (None, 0) or base is None: return ""
                    try: return round(100.0 * (float(cur) - float(base)) / float(base), 2)
                    except Exception: return ""
                ate_d = pct(m.get("ate_rmse"), base_m.get("ate_rmse") if base_m else None) if variant != "baseline" else 0.0
                rpe_d = pct(m.get("rpe_trans_med"), base_m.get("rpe_trans_med") if base_m else None) if variant != "baseline" else 0.0
                row = [grade, run, variant, m.get("ate_rmse"), m.get("ate_mean"), m.get("rpe_trans_med"),
                       m.get("early_scale"), m.get("late_scale"), m.get("vins_failures"), m.get("n_vio"),
                       orr, fmgr, 1 if m.get("diverged") else 0, det_ok, ate_d, rpe_d, outdir]
                rows.append(row)
                with open(CSV, "a") as f:
                    f.write(",".join("" if v is None else str(v) for v in row) + "\n")
                print(f"[vs] {grade}/{run}/{variant}: ate={m.get('ate_rmse')} d_ate%={ate_d} d_rpe%={rpe_d} fail={m.get('vins_failures')} det_ok={det_ok}")
            # classify this (grade,run)
            perturb = [r for r in rows if r[0] == grade and r[1] == run and r[2] in ("cull_off", "all_object_mask", "oracle_mask")]
            base_row = [r for r in rows if r[0] == grade and r[1] == run and r[2] == "baseline"][0]
            fails = any((str(r[8]) not in ("0", "None", "") and r[8]) for r in perturb + [base_row]) or base_row[12] == 1
            max_ate = max([abs(float(r[14])) for r in perturb if r[14] not in ("", None)] + [0.0])
            max_rpe = max([abs(float(r[15])) for r in perturb if r[15] not in ("", None)] + [0.0])
            if fails or (base_row[9] and int(base_row[9]) < 300):
                cls = "UNSTABLE"
            elif max_ate >= ACTIVE_ATE_PCT or max_rpe >= ACTIVE_RPE_PCT:
                cls = "VISION_ACTIVE"
            else:
                cls = "VISION_INERT"
            classify[(grade, run)] = (cls, round(max_ate, 2), round(max_rpe, 2))
            print(f"  === {grade}/{run}: {cls} (max|dATE|={max_ate:.2f}% max|dRPE|={max_rpe:.2f}%) ===")
    print("\n=== CLASSIFICATION ===")
    for k, v in classify.items():
        print(f"  {k[0]:16s} {k[1]:10s} -> {v[0]:14s} maxdATE={v[1]}% maxdRPE={v[2]}%")
    (WS / "paper2/track_a/paper2_vision_sensitivity_classify.json").write_text(
        json.dumps({f"{k[0]}|{k[1]}": v for k, v in classify.items()}, indent=2))
    print("VS_GATE_DONE")


if __name__ == "__main__":
    main()
