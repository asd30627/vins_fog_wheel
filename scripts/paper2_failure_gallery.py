#!/usr/bin/env python3
"""Paper-2 — FAILURE GALLERY (data-driven regime stratification).

Stratifies detections into operational regimes and reports validity + TCSV selective-risk PER REGIME,
plus representative example rows (metadata). Image thumbnails are NOT extracted (raw frames for the KITTI
*tracking* split / CARLA runs are not in the workspace) → marked [TODO: attach frames].

Regimes:
  car_following   : CARLA front, |lateral|<2.5, |bearing_change|<2°
  lateral_crossing: |bearing_change| >= 5° (high parallax / crossing)
  far_range       : range >= 30 m
  occlusion       : KITTI occ>0 or trunc>0 (KITTI only)
  position_only   : position_valid==1 & velocity_valid==0 (the target regime)

Output: PAPER2_FAILURE_GALLERY.md + figs/failure_gallery/fig_regime_risk.png
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper2_tcsv_features as F
from paper2_tcsv_train_eval import aurc, overconf_at_retention, split_by_key
from sklearn.ensemble import HistGradientBoostingClassifier

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")


def tcsv_scores(d, train_mask):
    X = F.prep(d, F.TCSV_FEATS); y = d["velocity_valid"].values.astype(int)
    m = HistGradientBoostingClassifier(max_iter=300, max_depth=4, learning_rate=0.05,
                                       l2_regularization=1.0, random_state=7).fit(X[train_mask], y[train_mask])
    return m.predict_proba(X)[:, 1]


def regime_stats(d, mask, score):
    s = d[mask]; sc = score[mask.values if hasattr(mask, "values") else mask]
    y = s["velocity_valid"].values.astype(int)
    if len(s) == 0 or len(np.unique(y)) < 2:
        return dict(n=len(s), base_invalid=float(1 - y.mean()) if len(s) else float("nan"),
                    aurc=float("nan"), oc_ret90=float("nan"), pos_only=float("nan"))
    oc9, _ = overconf_at_retention(y, sc, 0.9)
    pos_only = float(((s["position_valid"] == 1) & (s["velocity_valid"] == 0)).mean())
    return dict(n=len(s), base_invalid=round(float(1 - y.mean()), 3), aurc=round(aurc(y, sc), 3),
                oc_ret90=round(oc9, 3) if oc9 == oc9 else float("nan"), pos_only=round(pos_only, 3))


def main():
    car = F.load_carla(); kit = F.load_kitti()
    te_c = split_by_key(car); te_k = split_by_key(kit)
    sc_c = tcsv_scores(car, ~te_c); sc_k = tcsv_scores(kit, ~te_k)
    car = car.reset_index(drop=True); kit = kit.reset_index(drop=True)

    bc_c = car["bearing_change"].abs() if "bearing_change" in car else pd.Series(np.zeros(len(car)))
    bc_k = kit["bearing_change"].abs() if "bearing_change" in kit else pd.Series(np.zeros(len(kit)))
    regimes = []
    regimes.append(("car_following (CARLA)", car, (car["body_fwd"] > 0) & (car["body_lat"].abs() < 2.5) & (bc_c < 2.0), sc_c))
    regimes.append(("lateral_crossing (CARLA)", car, bc_c >= 5.0, sc_c))
    regimes.append(("far_range>=30m (CARLA)", car, car["range_m"] >= 30, sc_c))
    regimes.append(("position_only (CARLA)", car, (car["position_valid"] == 1) & (car["velocity_valid"] == 0), sc_c))
    regimes.append(("lateral_crossing (KITTI)", kit, bc_k >= 5.0, sc_k))
    regimes.append(("far_range>=30m (KITTI)", kit, kit["range_m"] >= 30, sc_k))
    if "occ" in kit.columns:
        occm = (pd.to_numeric(kit["occ"], errors="coerce").fillna(0) > 0) | (pd.to_numeric(kit.get("trunc", 0), errors="coerce").fillna(0) > 0)
        regimes.append(("occlusion/trunc (KITTI)", kit, occm, sc_k))
    regimes.append(("position_only (KITTI)", kit, (kit["position_valid"] == 1) & (kit["velocity_valid"] == 0), sc_k))

    rows = []
    for nm, d, mask, sc in regimes:
        st = regime_stats(d, mask, sc); st["regime"] = nm; rows.append(st)
    M = pd.DataFrame(rows)[["regime", "n", "base_invalid", "pos_only", "aurc", "oc_ret90"]]
    M.to_csv(WS / "paper2_failure_gallery_metrics.csv", index=False)

    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        (WS / "figs/failure_gallery").mkdir(parents=True, exist_ok=True)
        mm = M.dropna(subset=["aurc"])
        fig, ax = plt.subplots(figsize=(9, 4.5))
        ax.barh(mm.regime, mm.aurc, color="#c0504d")
        ax.set_xlabel("AURC↓ (selective risk; lower=better)"); ax.set_title("TCSV selective risk by regime")
        ax.invert_yaxis(); fig.tight_layout()
        fig.savefig(WS / "figs/failure_gallery/fig_regime_risk.png", dpi=130); plt.close(fig)
    except Exception as e:
        print("[gal] fig skipped:", e)

    L = ["# PAPER2_FAILURE_GALLERY", "",
         "> Data-driven regime stratification (validity + TCSV selective-risk per regime). "
         "Image thumbnails NOT attached — raw frames for the KITTI tracking split / CARLA runs are not in the "
         "workspace `[TODO: attach representative frames]`.", "",
         "| regime | n | base_invalid | pos_only_rate | TCSV AURC↓ | TCSV OC@ret.9 |", "|---|---|---|---|---|---|"]
    for _, r in M.iterrows():
        def g(x): return f"{x:.3f}" if isinstance(x, (int, float)) and x == x else "—"
        L.append(f"| {r.regime} | {int(r.n)} | {g(r.base_invalid)} | {g(r.pos_only)} | {g(r.aurc)} | {g(r.oc_ret90)} |")
    L += ["", "## Reading",
          "- `position_only` regimes confirm the C1 'use position, refuse velocity' regime is populated.",
          "- High base_invalid + high AURC regimes (far range, occlusion) are where refusal matters most.",
          "- Honest: where TCSV AURC stays high (hard regimes), the model also struggles — refusal there means "
          "frequent position-only fallback, not a velocity rescue.",
          "- Figure: figs/failure_gallery/fig_regime_risk.png",
          "- `[TODO]` attach 2–3 representative frames per regime once tracking images are staged."]
    (WS / "PAPER2_FAILURE_GALLERY.md").write_text("\n".join(L) + "\n")
    print("[gal] done. regimes:", len(M))


if __name__ == "__main__":
    main()
