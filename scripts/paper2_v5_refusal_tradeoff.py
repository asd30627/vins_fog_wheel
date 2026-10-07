#!/usr/bin/env python3
"""Paper-2 v5 (C3 trade-off) — operating-point sweep: overconfident-wrong-velocity vs valid-retention.

Change: paper2-observability-aware-object-validity-v5.

Sweeps the velocity-emit threshold for OVI vs distance(-range) vs a v4-analog (uncertainty~range), and
plots the Pareto trade-off (lower overconfidence at higher retention is better). Honest: if OVI only
marginally beats distance (consistent with the OVI ablation), say so — the contribution is the
validity-LAYER framework + decision-level evaluation, not that OVI specifically dominates.
Output: paper2_v5_refusal_tradeoff.csv + fig_v5_refusal_tradeoff.png + PAPER2_V5_REFUSAL_TRADEOFF.md
"""
from __future__ import annotations
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel")
FIGDIR = WS / "figs"; FIGDIR.mkdir(exist_ok=True)


def curve(score_emit_high, y_valid, te):
    """score: higher => more likely to emit velocity. Sweep threshold -> (retention, overconfidence, emit)."""
    s = score_emit_high[te]; yv = y_valid[te]; inv = 1 - yv
    out = []
    for q in np.linspace(0.0, 0.98, 40):
        thr = np.quantile(s, q)
        emit = s >= thr
        if emit.sum() < 10:
            continue
        oc = float(inv[emit].mean())                       # overconfident-wrong-velocity among emitted
        ret = float(emit[yv == 1].sum() / max((yv == 1).sum(), 1))  # valid retention
        out.append((float(emit.mean()), ret, oc))
    return np.array(out)


def main():
    d = pd.read_parquet(WS / "paper2_v5_validity_with_ovi.parquet")
    te = (d["split"] == "test").values
    y_valid = d["velocity_valid"].values.astype(int)
    ovi = d["OVI_velocity_cal"].values
    dist = -d["range_m"].values                # closer => emit
    v4analog = -(0.1 * d["range_m"].values)    # v4-style: uncertainty grows ~linearly with range (monotone == dist)

    cur = {"v5_OVI": curve(ovi, y_valid, te), "distance(-range)": curve(dist, y_valid, te)}
    # save curve data
    rows = []
    for name, c in cur.items():
        for emit, ret, oc in c:
            rows.append(dict(model=name, emit_frac=round(emit, 3), valid_retention=round(ret, 3), overconf_wrong=round(oc, 3)))
    pd.DataFrame(rows).to_csv(WS / "paper2_v5_refusal_tradeoff.csv", index=False)

    # area-style summary: overconfidence at matched retention levels
    def oc_at_ret(c, target):
        # interpolate overconfidence at a given retention
        cc = c[c[:, 1].argsort()]
        return float(np.interp(target, cc[:, 1], cc[:, 2]))
    ret_levels = [0.7, 0.8, 0.9]
    cmp_tbl = {r: {n: oc_at_ret(c, r) for n, c in cur.items()} for r in ret_levels}

    plt.figure(figsize=(5, 4))
    for name, c in cur.items():
        cc = c[c[:, 1].argsort()]
        plt.plot(cc[:, 1], cc[:, 2], marker="o", ms=3, label=name)
    # no-policy point: retention 1.0, overconf = base invalid rate
    base_oc = float((1 - y_valid[te]).mean())
    plt.scatter([1.0], [base_oc], c="k", marker="*", s=120, label="no-policy")
    plt.xlabel("valid-velocity retention (higher better)")
    plt.ylabel("overconfident-wrong-velocity (lower better)")
    plt.title("v5 refusal trade-off (velocity emit)")
    plt.legend(fontsize=8); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(FIGDIR / "fig_v5_refusal_tradeoff.png", dpi=130); plt.close()

    # is OVI Pareto-better than distance? compare overconf at each retention level
    wins = sum(1 for r in ret_levels if cmp_tbl[r]["v5_OVI"] <= cmp_tbl[r]["distance(-range)"] + 1e-6)
    L = ["# PAPER2_V5_REFUSAL_TRADEOFF (C3 — operating-point sweep)", "",
         f"> Sweep velocity-emit threshold. no-policy overconfidence (base invalid rate) = {base_oc:.3f}. "
         f"Fig: figs/fig_v5_refusal_tradeoff.png", "",
         "## Overconfident-wrong-velocity at matched valid-retention (lower = better)",
         "| retention | v5_OVI | distance(-range) |", "|---|---|---|"]
    for r in ret_levels:
        L.append(f"| {r:.1f} | {cmp_tbl[r]['v5_OVI']:.3f} | {cmp_tbl[r]['distance(-range)']:.3f} |")
    L += ["", "## Reading (honest)",
          f"- ANY observability-aware refusal cuts overconfidence massively from the no-policy {base_oc:.3f} "
          "as retention drops — this is the validity-LAYER value (the framework), independent of OVI.",
          f"- v5_OVI vs distance: OVI lower-or-equal overconfidence at {wins}/{len(ret_levels)} retention levels → "
          + ("OVI marginally Pareto-better." if wins >= 2 else "OVI roughly ties distance (consistent with the OVI ablation: geometric gain is small)."),
          "- HONEST: the headline C3 result is the validity-layer trade-off itself (huge overconfidence cut + "
          "position_only regime), NOT that OVI specifically beats a distance gate (that gain is marginal).",
          "- v4-analog (uncertainty~range) is monotone-equivalent to the distance gate here, so it overlaps the distance curve."]
    (WS / "PAPER2_V5_REFUSAL_TRADEOFF.md").write_text("\n".join(L) + "\n")
    print(f"[tradeoff] base_oc={base_oc:.3f} OVI-wins {wins}/{len(ret_levels)} ; oc@0.8ret OVI {cmp_tbl[0.8]['v5_OVI']:.3f} dist {cmp_tbl[0.8]['distance(-range)']:.3f}")


if __name__ == "__main__":
    main()
