# EXPERIMENT GAP AUDIT — Paper-2 Draft v0.1

> Every place a reviewer can currently attack the experimental record, with status. Honest: DONE = run this round.
> Cross-ref: `PAPER2_FULL_MISSING_EXPERIMENTS_PLAN.md` (P0/P1/P2), `REVIEWER_ATTACK_PLAN.md` (rebuttals).

## Gap → status → residual risk

| area | gap | status | residual reviewer risk |
|---|---|---|---|
| **Baselines** | only distance/OVI before | **DONE** — 9 baselines × 6 splits (`PAPER2_PUBLIC_PROXY_BASELINE_RESULTS.md`) | SelectiveNet is a proxy ≈ our MLP; qiu is a proxy. Medium. |
| **Strong simple baseline** | is the model needed at all? | **EXPOSED** — cv_smoothing_gate beats TCSV on direct transfer | "your model barely beats / loses to a one-liner". **High** — must frame as supporting the thesis. |
| **Leakage** | unproven no-GT claim | **DONE** — `PAPER2_LEAKAGE_AUDIT.md` (provenance + shuffle + single-feat + no GT∩) | Low. |
| **Grouping bug** | cross-town track merge inflated CARLA | **DONE/PARTIAL** — fixed in pipeline; 0.873→0.800; old report not yet edited (P0-1) | Low once P0-1 done. |
| **Threshold robustness** | claim predated fix | **DONE** — regrouped; C1 14/18 (loose-τ only), model 6/6 | Low; add dir sweep for parity (optional). |
| **Calibration** | is the score usable? | **DONE** — ECE 0.02–0.03 raw; post-hoc no help | Low. |
| **Planner relevance (C3)** | "so what for planning?" | **PARTIAL** — CARLA TTC supports C3 (0.214→0.156); KITTI TTC TODO | Medium — single dataset, range-rate TTC only. |
| **Data quality** | monocular KITTI depth | **TODO** — stereo redo pending (P0-5) | High — affects velocity & bbox_depth_consistency; numbers may move. |
| **Novelty vs Qiu** | overclaim risk | **PARTIAL** — proxy run; boundary table TODO (P0-6) | Medium-High — central novelty hinge. |
| **Feature value** | do new residuals help? | **DONE (negative)** — net neutral; reported honestly | Low if framed as formulation contribution; High if oversold. |
| **Cross-domain** | generalization | **DONE** — 4 transfer splits; direct weak, mixed-train recovers | Medium — direct transfer weak. |
| **Stats rigor** | no CIs | **TODO (P2-4)** — no bootstrap CIs yet | Medium — small margins (CARLA +0.009) need CIs. |
| **Regime coverage** | failure modes | **PARTIAL** — data-driven gallery; no frames; CARLA lateral n=9 | Low-Medium. |
| **Importance story** | temporal claim | **DONE (permutation)** — SHAP figure TODO (P1-3) | Low. |

## The 4 highest-risk gaps (fix before submission)
1. **cv_smoothing beats TCSV on transfer** — reframe as evidence for the temporal-consistency thesis (cv_residual IS
   temporal-consistency) + show TCSV's value is in-domain/calibrated. Add bootstrap CIs so the small CARLA margin
   (+0.009) is defensible. (P2-4 + narrative)
2. **stereo KITTI redo** (P0-5) — biggest data-quality exposure.
3. **Qiu claim-boundary table** (P0-6) — protects novelty.
4. **CARLA in-domain margin is tiny (0.703 vs 0.712)** — needs CIs or it reads as noise; KITTI carries the win.

## Things that are now SOLID (defensible today)
- Phenomenon C1 (cross-dataset, threshold-robust, not collision artifact).
- No-leakage claim.
- Calibration (raw scores usable).
- In-domain + mixed-train selective-risk win on KITTI (large, clear).
- Honest negative results (residuals net-neutral, transfer weak) — strengthens credibility.
