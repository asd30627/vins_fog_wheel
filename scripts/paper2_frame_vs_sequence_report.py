#!/usr/bin/env python3
"""Generate PAPER2_FRAME_VS_SEQUENCE_RESULTS.md from the search CSVs (no recompute)."""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

OUT = Path("/home/ivlab3/fwvio_estimator_ws_wheel/paper2/track_a")


def g(x):
    try:
        return f"{float(x):.3f}"
    except Exception:
        return "—"


def main():
    M = pd.read_csv(OUT / "paper2_frame_vs_sequence_metrics.csv")
    SW = pd.read_csv(OUT / "paper2_frame_vs_sequence_seqsweep.csv")
    BT = pd.read_csv(OUT / "paper2_frame_vs_sequence_bootstrap.csv")
    ML = pd.read_csv(OUT / "paper2_frame_vs_sequence_multilabel.csv")
    meta = json.loads((OUT / "paper2_frame_vs_sequence_meta.json").read_text())

    L = ["# PAPER2 Part 1 — FRAME vs SEQUENCE RESULTS", "",
         f"> Object-state validity (velocity_valid primary). CARLA n={meta['n_carla']} (4 towns), "
         f"KITTI n={meta['n_kitti']}. Splits by group (CARLA town@run, KITTI kitti@seq) — NO frame-random, "
         f"no track in both train/test. Sequence windows PAST-ONLY (edge-pad earliest), no future leak. "
         f"Primary metric AURC (lower=better). torch={meta['has_torch']}. runtime={meta['runtime_s']}s. "
         f"Date 2026-07-01.", "",
         f"**Chosen deployable sequence config:** T={meta['SEQ_T']}, pool={meta['SEQ_POOL']} "
         f"(best combined in-domain AURC rank).", "",
         f"**BEST_PER_FRAME_MODEL = `{meta['BEST_PF']}`**  |  **BEST_SEQUENCE_MODEL = `{meta['BEST_SEQ']}`** "
         f"(by mean in-domain AURC).", "",
         "## 1. AURC↓ by split × model (primary)"]
    piv = M.pivot_table(index="split", columns="model", values="aurc", aggfunc="first")
    L.append(piv.round(4).to_markdown())
    L += ["", "## 2. Full operating metrics (velocity_valid)",
          "| split | family | model | AUROC | AURC↓ | OC@ret.8↓ | OC@ret.9↓ | retention | F1_inv | fit_ms |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in M.sort_values(["split", "family", "aurc"]).iterrows():
        L.append(f"| {r.split} | {r.family} | {r.model} | {g(r.auroc)} | {g(r.aurc)} | "
                 f"{g(r.get('overconf_at_ret80'))} | {g(r.get('overconf_at_ret90'))} | {g(r.retention)} | "
                 f"{g(r.f1_invalid)} | {g(r.fit_ms)} |")

    L += ["", "## 3. Sequence T × pooling sweep (in-domain AURC↓, pool_hgbm)"]
    for ds in ["carla", "kitti"]:
        sub = SW[SW.dataset == ds]
        p = sub.pivot_table(index="T", columns="pool", values="aurc")
        L += [f"", f"**{ds}**", p.round(4).to_markdown()]

    L += ["", "## 4. Paired bootstrap ΔAURC over groups (cand − ref); neg & CI<0 ⇒ cand better",
          "| split | comparison | ΔAURC | CI low | CI high | verdict |", "|---|---|---|---|---|---|"]
    for _, r in BT.iterrows():
        L.append(f"| {r.split} | {r.comparison} | {g(r.dAURC_mean)} | {g(r.ci_lo)} | {g(r.ci_hi)} | {r.verdict} |")

    L += ["", "## 5. Multi-label feasibility (position_valid, full_state_valid; in-domain)",
          "| label | dataset | model | n | base | AUROC | AURC↓ | OC@ret.9↓ |", "|---|---|---|---|---|---|---|---|"]
    for _, r in ML.iterrows():
        if str(r.get("model", "")).startswith("(skip"):
            L.append(f"| {r.label} | {r.dataset} | (skip: {r.get('note','')}) | | | | | |"); continue
        L.append(f"| {r.label} | {r.dataset} | {r.model} | {r.get('n','')} | {g(r.get('base'))} | "
                 f"{g(r.get('auroc'))} | {g(r.get('aurc'))} | {g(r.get('overconf_at_ret90'))} |")

    L += ["", "## 6. Per-frame model ranking (mean in-domain AURC↓)"]
    for k, v in meta["pf_rank"].items():
        L.append(f"- {k}: {v:.4f}")
    L += ["", "## 7. Sequence model ranking (mean in-domain AURC↓)"]
    for k, v in meta["seq_rank"].items():
        L.append(f"- {k}: {v:.4f}")

    (OUT / "PAPER2_FRAME_VS_SEQUENCE_RESULTS.md").write_text("\n".join(L) + "\n")
    print("[report] wrote PAPER2_FRAME_VS_SEQUENCE_RESULTS.md")
    print("[report] BEST_PF=", meta["BEST_PF"], "BEST_SEQ=", meta["BEST_SEQ"],
          "T=", meta["SEQ_T"], "pool=", meta["SEQ_POOL"])


if __name__ == "__main__":
    main()
