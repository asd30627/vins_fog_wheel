#!/usr/bin/env python3
"""
KAIST xsens IMU grade injection (step 3): inject Allan-variance grades onto KAIST's REAL xsens gyro
(xsens_imu.csv cols 8-10, rad/s) to synthesize 3 WORSE IMU grades on the real trajectory + real GT.
PURE DATA-LAYER op — no estimator/ROS/VINS. Mirrors gen_kaist_grade_fog.py inject() exactly, but:
  - xsens gyro is already ANGULAR RATE (rad/s) -> inject directly in rate domain (no incr<->rate convert).
  - all 17 columns preserved; only gyro cols [8,9,10] replaced with the degraded measurement.
  - real xsens (kaist_real_005) = ORIGINAL file, unchanged (best baseline point).

KAIST xsens_imu.csv (17 cols): [0]=ts_ns, [8:11]=gyro xyz (rad/s), [11:14]=accel xyz (m/s^2).
Input : <extracted>/<seq>/data/<seq>/sensor_data/xsens_imu.csv
Output: <...>/sensor_data/xsens_grade_<grade>.csv   (same 17-col format; gyro = injected)
Usage : python3 gen_kaist_grade_xsens.py --seq urban29-pankyo --grade industrial_fog [--seed 42]
        python3 gen_kaist_grade_xsens.py --seq urban29-pankyo           # all 3 grades
"""
import argparse, math
from pathlib import Path
import numpy as np

DEG2RAD = math.pi / 180.0
KAIST_ROOT = Path("/mnt/sata4t/datasets/kaist_complex_urban/extracted")

# Same 3 grades as the FOG script (worse than real). Gyro-domain Allan params.
PROFILES = {
    "industrial_fog": dict(arw=0.03, bias=0.3,  brw=0.005, scale_ppm=200),
    "precision_mems": dict(arw=0.15, bias=5.0,  brw=0.05,  scale_ppm=1000),
    "general_imu":    dict(arw=0.3,  bias=10.0, brw=0.1,   scale_ppm=2000),
}
REAL_GRADE = "kaist_real_005"


def inject(ts_s, gyr_clean, prof, seed):
    """Identical model/units/draw-order to gen_kaist_grade_fog.py inject(). ts_s sec, gyr_clean (n,3) rad/s."""
    arw = prof["arw"] * DEG2RAD / 60.0
    bias_sig = prof["bias"] * DEG2RAD / 3600.0
    brw_den = prof["brw"] * DEG2RAD / 3600.0
    scale_sig = prof["scale_ppm"] * 1e-6
    rng = np.random.RandomState(int(seed))
    const_bias = rng.randn(3) * bias_sig
    scale_err = rng.randn(3) * scale_sig
    n = len(ts_s)
    dts = np.diff(ts_s, prepend=ts_s[0]); dts[0] = (ts_s[1] - ts_s[0]) if n > 1 else 1e-3
    dts = np.maximum(dts, 1e-6)
    wn = rng.randn(n, 3) * (arw / np.sqrt(dts))[:, None]
    brw = np.cumsum(brw_den * np.sqrt(dts)[:, None] * rng.randn(n, 3), axis=0)
    return (1.0 + scale_err) * gyr_clean + const_bias + brw + wn


def sd_dir(seq):
    return KAIST_ROOT / seq / "data" / seq / "sensor_data"


def process(seq, grade, seed):
    sd = sd_dir(seq); src = sd / "xsens_imu.csv"
    if not src.exists():
        print(f"[skip] {seq}: no xsens_imu.csv"); return
    # keep raw text rows to preserve ALL columns exactly; only rewrite gyro cols 8-10
    rows = [ln.rstrip("\n").split(",") for ln in src.read_text().splitlines() if ln.strip()]
    rows = [r for r in rows if len(r) >= 17]
    ts_ns = np.array([int(r[0]) for r in rows], dtype=np.int64)
    gyr = np.array([[float(r[8]), float(r[9]), float(r[10])] for r in rows], dtype=float)
    ts_s = ts_ns * 1e-9
    gyr_meas = inject(ts_s, gyr, PROFILES[grade], seed)
    out = sd / f"xsens_grade_{grade}.csv"
    with open(out, "w") as f:
        for i, r in enumerate(rows):
            r = list(r)
            r[8] = f"{gyr_meas[i,0]:.12e}"; r[9] = f"{gyr_meas[i,1]:.12e}"; r[10] = f"{gyr_meas[i,2]:.12e}"
            f.write(",".join(r) + "\n")
    cn = np.linalg.norm(gyr, axis=1); mn = np.linalg.norm(gyr_meas, axis=1)
    print(f"[ok] {seq}/{grade}: n={len(rows)} clean|g|med={np.median(cn):.3e} meas|g|med={np.median(mn):.3e} -> {out.name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq", required=True)
    ap.add_argument("--grade", default=None, choices=list(PROFILES))
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    grades = [a.grade] if a.grade else list(PROFILES)
    for g in grades:
        process(a.seq, g, a.seed)
    print(f"NOTE: {REAL_GRADE} uses ORIGINAL xsens_imu.csv unchanged (best baseline point).")


if __name__ == "__main__":
    main()
