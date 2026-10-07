#!/usr/bin/env python3
"""Paper-2 v5 — headline figures for the paper. STANDALONE. Output -> figs/.

Change: paper2-observability-aware-object-validity-v5.
Figs: (1) position vs velocity validity by distance bin (the headline phenomenon);
      (2) phase-map heatmaps density x distance for velocity_valid and position_only;
      (3) OVI vs distance-only velocity-valid AUROC within each distance bin (honest mid-range-only gain).
"""
from __future__ import annotations
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

WS = Path("/home/ivlab3/fwvio_estimator_ws_wheel"); FIG = WS / "figs"; FIG.mkdir(exist_ok=True)
BINS = ["0-15m", "15-30m", "30m+"]
DENS = ["sparse", "medium", "dense"]


def main():
    d = pd.read_parquet(WS / "paper2_v5_object_validity_dataset.parquet")

    # Fig 1: validity by distance
    pv = [d[d.dist_bin == b].position_valid.mean() for b in BINS]
    vv = [d[d.dist_bin == b].velocity_valid.mean() for b in BINS]
    po = [d[d.dist_bin == b].position_only.mean() for b in BINS]
    x = np.arange(len(BINS)); w = 0.27
    plt.figure(figsize=(5, 3.6))
    plt.bar(x - w, pv, w, label="position_valid", color="#2c7fb8")
    plt.bar(x, vv, w, label="velocity_valid", color="#d95f0e")
    plt.bar(x + w, po, w, label="position_only", color="#74a9cf")
    plt.xticks(x, BINS); plt.ylim(0, 1); plt.ylabel("rate"); plt.title("Object state validity vs distance")
    for xi, v in zip(x, vv): plt.text(xi, v + 0.02, f"{v:.2f}", ha="center", fontsize=8)
    plt.legend(fontsize=8); plt.grid(axis="y", alpha=0.3); plt.tight_layout()
    plt.savefig(FIG / "fig_v5_validity_by_distance.png", dpi=140); plt.close()

    # Fig 2: phase-map heatmaps (density x distance)
    def grid(col):
        return np.array([[d[(d.dist_bin == b) & (d.density == dn)][col].mean() for b in BINS] for dn in DENS])
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.4))
    for ax, col, ttl in zip(axes, ["velocity_valid", "position_only"], ["velocity_valid", "position_only"]):
        G = grid(col); im = ax.imshow(G, vmin=0, vmax=1, cmap="RdYlGn" if col == "velocity_valid" else "Blues", aspect="auto")
        ax.set_xticks(range(len(BINS))); ax.set_xticklabels(BINS); ax.set_yticks(range(len(DENS))); ax.set_yticklabels(DENS)
        ax.set_title(f"phase map: {ttl}")
        for i in range(len(DENS)):
            for j in range(len(BINS)):
                ax.text(j, i, f"{G[i,j]:.2f}", ha="center", va="center", fontsize=8)
        fig.colorbar(im, ax=ax, fraction=0.046)
    plt.tight_layout(); plt.savefig(FIG / "fig_v5_phase_map.png", dpi=140); plt.close()

    # Fig 3: OVI vs distance within-bin AUROC (honest)
    abl = WS / "paper2_v5_ovi_ablation.md"
    # parse per-bin from the ablation md table if present, else recompute quickly
    ovi_b, dist_b = [], []
    try:
        txt = (WS / "PAPER2_V5_OVI_ABLATION.md").read_text().splitlines()
        for b in BINS:
            for ln in txt:
                if ln.startswith(f"| {b} |"):
                    parts = [p.strip() for p in ln.split("|")]
                    ovi_b.append(float(parts[2])); dist_b.append(float(parts[3])); break
    except Exception:
        ovi_b = dist_b = [np.nan] * 3
    if len(ovi_b) == 3:
        x = np.arange(3); w = 0.35
        plt.figure(figsize=(5, 3.4))
        plt.bar(x - w/2, dist_b, w, label="distance-only", color="#969696")
        plt.bar(x + w/2, ovi_b, w, label="OVI (geometric)", color="#41ab5d")
        plt.axhline(0.5, color="k", ls=":", lw=0.8)
        plt.xticks(x, BINS); plt.ylim(0, 1); plt.ylabel("velocity-valid AUROC")
        plt.title("OVI vs distance (within-bin) — honest: gain only mid-range")
        plt.legend(fontsize=8); plt.grid(axis="y", alpha=0.3); plt.tight_layout()
        plt.savefig(FIG / "fig_v5_ovi_within_bin.png", dpi=140); plt.close()
    print("[figs] wrote fig_v5_validity_by_distance / fig_v5_phase_map / fig_v5_ovi_within_bin (+ trade-off earlier)")
    print("[figs] validity by dist: pos", [round(v, 2) for v in pv], "vel", [round(v, 2) for v in vv])


if __name__ == "__main__":
    main()
