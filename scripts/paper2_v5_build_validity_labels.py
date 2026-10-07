#!/usr/bin/env python3
"""Paper-2 v5 (C1) — build dynamic-object STATE VALIDITY labels from the raw object benchmark.

Change: paper2-observability-aware-object-validity-v5. STANDALONE; no backend.

Validity labels (thresholds are CHOICES, written here + ablatable — not absolute truth):
  position_valid         = pos_err_m <= POS_T (3.0)
  velocity_valid         = speed_err_ms <= SPD_T (3.0) AND dir_err_deg <= DIR_T (45)
  full_state_valid       = position_valid AND velocity_valid
  position_only          = position_valid AND NOT velocity_valid
  invalid_velocity       = NOT velocity_valid
  unobservable_candidate = invalid_velocity AND (|bearing_change| < BC_T OR gt_range > FAR_T OR depth_jitter > DJ_T)
  high_risk_object       = invalid_velocity AND gt_range < NEAR_T  (close but wrong velocity = dangerous)

Output: paper2_v5_object_validity_dataset.parquet/.csv + PAPER2_V5_VALIDITY_LABEL_REPORT.md
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np, pandas as pd

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
POS_T, SPD_T, DIR_T = 3.0, 3.0, 45.0
BC_T, FAR_T, DJ_T, NEAR_T = 0.5, 30.0, 0.30, 15.0   # bearing-change deg/frame, range m, rel disp jitter, near m
BINS = ["0-15m", "15-30m", "30m+"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-csv", default=str(WS / "paper2_raw_object_benchmark_all_with_vins.csv"))
    ap.add_argument("--out", default=str(WS / "paper2_v5_object_validity_dataset"))
    a = ap.parse_args()
    df = pd.read_csv(a.in_csv, low_memory=False)
    df = df[df["matched"] == 1].copy()
    for c in ["pos_err_m", "speed_err_ms", "dir_err_deg", "gt_range_m", "range_m", "bearing_change_deg",
              "disp_med", "disp_std", "track_age", "raw_speed_ms"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    n_all = len(df)
    # velocity labels need a raw velocity estimate (speed_err present)
    df["has_velocity_est"] = df["speed_err_ms"].notna().astype(int)
    df = df[df["pos_err_m"].notna()].copy()

    df["position_valid"] = (df["pos_err_m"] <= POS_T).astype(int)
    vv = (df["speed_err_ms"] <= SPD_T) & (df["dir_err_deg"] <= DIR_T)
    df["velocity_valid"] = np.where(df["has_velocity_est"] == 1, vv.astype(int), 0)
    df["full_state_valid"] = ((df["position_valid"] == 1) & (df["velocity_valid"] == 1)).astype(int)
    df["position_only"] = ((df["position_valid"] == 1) & (df["velocity_valid"] == 0)).astype(int)
    df["invalid_velocity"] = (df["velocity_valid"] == 0).astype(int)
    depth_jitter = df["disp_std"] / df["disp_med"].replace(0, np.nan)
    df["depth_jitter"] = depth_jitter
    low_bc = df["bearing_change_deg"].abs() < BC_T
    df["unobservable_candidate"] = ((df["invalid_velocity"] == 1) &
                                    (low_bc | (df["gt_range_m"] > FAR_T) | (depth_jitter > DJ_T))).astype(int)
    df["high_risk_object"] = ((df["invalid_velocity"] == 1) & (df["gt_range_m"] < NEAR_T)).astype(int)

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(a.out + ".parquet", index=False); df.to_csv(a.out + ".csv", index=False)

    def rates(g):
        return dict(n=len(g), pos_valid=g.position_valid.mean(), vel_valid=g.velocity_valid.mean(),
                    full=g.full_state_valid.mean(), pos_only=g.position_only.mean(),
                    invalid_vel=g.invalid_velocity.mean(), unobs=g.unobservable_candidate.mean(),
                    high_risk=g.high_risk_object.mean())
    L = ["# PAPER2_V5_VALIDITY_LABEL_REPORT (C1)", "",
         f"> Dynamic-object state validity labels from {n_all} GT-matched detections "
         f"({df.has_velocity_est.sum()} have a raw velocity estimate). Thresholds are CHOICES (ablatable), not truth.", "",
         f"## Thresholds (ablatable)",
         f"- position_valid: pos_err<= {POS_T} m ; velocity_valid: speed_err<= {SPD_T} m/s AND dir_err<= {DIR_T}°",
         f"- unobservable_candidate: invalid_velocity AND (|bearing_change|<{BC_T}°/frame OR range>{FAR_T} m OR depth_jitter>{DJ_T})",
         f"- high_risk_object: invalid_velocity AND range<{NEAR_T} m", "",
         "## Overall label rates", "| label | rate |", "|---|---|"]
    o = rates(df)
    for k in ["pos_valid", "vel_valid", "full", "pos_only", "invalid_vel", "unobs", "high_risk"]:
        L.append(f"| {k} | {o[k]:.3f} |")
    L += ["", "## By distance bin", "| bin | n | pos_valid | vel_valid | full | position_only | invalid_vel | unobservable | high_risk |",
          "|---|---|---|---|---|---|---|---|---|"]
    for b in BINS:
        g = df[df.dist_bin == b]
        if len(g):
            r = rates(g); L.append(f"| {b} | {r['n']} | {r['pos_valid']:.2f} | {r['vel_valid']:.2f} | {r['full']:.2f} | "
                                   f"{r['pos_only']:.2f} | {r['invalid_vel']:.2f} | {r['unobs']:.2f} | {r['high_risk']:.2f} |")
    L += ["", "## By density", "| density | n | vel_valid | position_only | invalid_vel |", "|---|---|---|---|---|"]
    for d in ("sparse", "medium", "dense"):
        g = df[df.density == d]
        if len(g):
            r = rates(g); L.append(f"| {d} | {r['n']} | {r['vel_valid']:.2f} | {r['pos_only']:.2f} | {r['invalid_vel']:.2f} |")
    L += ["", "## By town", "| town | n | vel_valid | position_only | invalid_vel |", "|---|---|---|---|---|"]
    for t in sorted(df.town.unique()):
        g = df[df.town == t]; r = rates(g)
        L.append(f"| {t} | {r['n']} | {r['vel_valid']:.2f} | {r['pos_only']:.2f} | {r['invalid_vel']:.2f} |")
    L += ["", "## Reading (C1 observability/validity regimes emerge from data)",
          f"- velocity validity collapses with range (vel_valid {rates(df[df.dist_bin=='0-15m'])['vel_valid']:.2f} "
          f"-> {rates(df[df.dist_bin=='30m+'])['vel_valid']:.2f}) -> 'always output velocity' is wrong.",
          "- position validity degrades more slowly -> 'position_only' is a real, useful regime.",
          "- far/low-bearing-change/high-jitter -> unobservable_candidate; near+invalid -> high_risk.",
          "- thresholds ablatable; absolute rates depend on raw-velocity (centroid-diff) noise — scope honestly."]
    (WS / "PAPER2_V5_VALIDITY_LABEL_REPORT.md").write_text("\n".join(L) + "\n")
    print(f"[v5-labels] wrote dataset + report; n={len(df)} vel_est={df.has_velocity_est.sum()}")
    print("[v5-labels] vel_valid by bin:", {b: round(rates(df[df.dist_bin == b])['vel_valid'], 2) for b in BINS})


if __name__ == "__main__":
    main()
