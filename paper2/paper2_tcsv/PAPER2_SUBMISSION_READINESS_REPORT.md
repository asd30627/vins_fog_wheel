# PAPER2 — SUBMISSION READINESS REPORT

> Honest integration after Part C (baselines) + Part D (defenses). Topic fixed:
> **Temporal-Consistency-Aware Selective Object State Validity for GPS-Denied Navigation.**
> No frontier/planning main contribution, no VINS backend change, no localization claim. Date 2026-06-30.

---

## 1. 現在還缺哪些 P0？

| P0 | status |
|---|---|
| CARLA grouping fix in OLD reports | 🟡 **almost** — fixed in pipeline + new reports; one edit left: scrub 0.873 from `PAPER2_SELECTIVE_VALIDITY_RESULTS.md` |
| threshold robustness after fix | ✅ DONE (`PAPER2_THRESHOLD_ROBUSTNESS_REGROUPED.md`: C1 14/18, model 6/6) |
| leakage audit / provenance | ✅ DONE (`PAPER2_LEAKAGE_AUDIT.md`) |
| public/proxy baselines | ✅ DONE (`PAPER2_PUBLIC_PROXY_BASELINE_RESULTS.md`, 11 models × 6 splits) |
| **stereo KITTI redo** | ⬜ **NOT DONE** — true blocker |
| **Qiu 2018 claim-boundary table** | ⬜ **NOT DONE** — true blocker |

**Remaining P0 = 2 hard blockers (stereo KITTI, Qiu table) + 1 trivial edit.** Everything else in P0 is done.

## 2. 哪些 baseline 跑完，哪些只是 proxy？

**Real, fully run (9 + 3 = all 6 splits):** no_policy, distance_gate, yolo_conf_gate, bbox_depth_gate,
cv_smoothing_gate, ovi_geom, TCSV-rule/HistGBM/MLP. These are genuine.

**Proxies (clearly labeled, NOT equal to originals):**
- `qiu_style(proxy)` — our reimplementation of a Qiu-2018-style geometric-excitation/observability gate (logistic
  on range/|bearing-change|/track-age/bbox-area). Not the original pipeline.
- `selectivenet_proxy` — softmax-response selector of an MLP; **collapses to ≈ TCSV-MLP**. A full joint-trained
  SelectiveNet (predictor+selector+coverage loss) needs torch (unavailable) → `[TODO]`.

## 3. TCSV 是否仍贏 public/proxy baselines？

**部分贏，誠實混合（AURC↓）:**
- **In-domain & mixed-train: YES.** KITTI 0.210 (best non-ours cv_smoothing 0.288); held-out-KITTI 0.213 (selnet
  0.236); held-out-CARLA 0.685 (qiu 0.718); CARLA-in-domain 0.703 (qiu 0.712, **margin only −0.009**).
- **Direct cross-dataset: NO.** CARLA→KITTI 0.406 **loses** to cv_smoothing 0.327; KITTI→CARLA 0.823 loses to qiu
  0.805 (all models poor here, base-invalid 0.89).

**Key honest point:** the strongest simple baseline is `cv_smoothing_gate` (constant-velocity residual). It is a
pure temporal-consistency statistic, so its strength **supports** C2's thesis but **undercuts** "you need a model"
on transfer. Frame TCSV as the in-domain/calibrated improvement, not a universal winner. CARLA in-domain margin
needs bootstrap CIs.

## 4. stereo KITTI redo 是否改變主要結論？

**未知 — 尚未執行（P0-5）。** Expected impact: monocular bbox-height depth inflates depth noise with range and
confounds `bbox_depth_consistency` and velocity labels. Stereo should (a) clean velocity GT, (b) possibly raise
`cv_residual`/`bbox_depth_consistency` value, (c) shift absolute KITTI numbers. The *direction* of C1 (velocity
collapses with range, position stabler) is very unlikely to flip, but absolute AURC and the residual-importance
ranking may move. **Do not freeze KITTI numbers before this.**

## 5. leakage audit 是否乾淨？

**乾淨。** (`PAPER2_LEAKAGE_AUDIT.md`)
- 14 features ∩ GT columns = EMPTY (CARLA & KITTI).
- max single-feature AUROC = **0.827** (raw_speed) — far from a leak signature (~0.99).
- shuffled-label AUROC ≈ **0.5** ⇒ no structural leak.
- GT-feature ceiling shown separately and never used by TCSV.

## 6. planner-facing minimal evaluation 是否支持 C3？

**Modestly YES (CARLA).** (`PAPER2_PLANNER_TTC_RESULTS.md`) Refusal at 80% coverage cuts overconfident invalid
velocities accepted by the TTC check **0.214→0.156 (−27%)** and false alarms **0.200→0.140**, missed_risk ~flat
(0.024→0.028). Caveats: single dataset, range-rate TTC only, KITTI TTC + position-only fallback are `[TODO]`.
Sufficient as a *minimal decision-level probe*; not a planner (red line held).

## 7. 最適合投哪裡：IV / ITSC / RA-L / T-IV？

**建議順序：**
1. **IEEE IV 2026 / ITSC 2026 (conference) — 最合適起點。** Honest mixed results + strong phenomenon + selective-risk
   framing fit a focused conference; the "CV-gate wins on transfer" honesty is acceptable there.
2. **RA-L** — possible IF stereo redo + Qiu table + bootstrap CIs land and the in-domain story holds; RA-L tolerates
   a focused contribution with solid evaluation.
3. **T-IV (journal)** — only after stereo redo + full SelectiveNet + KITTI TTC + CIs + third-dataset; current
   transfer weakness and small CARLA margin are too exposed for a top journal now.

**判斷：今天的成熟度 ≈ IV/ITSC。 補完 P0-5/P0-6 + CIs → RA-L。 想要 T-IV 需再一輪。**

## 8. 只能再做 3 件事，哪 3 件最提高中稿率？

1. **stereo KITTI redo (P0-5)** — removes the single biggest data-quality attack (R2) and de-risks every KITTI number.
2. **Qiu claim-boundary table + verify qiu-proxy (P0-6)** — protects the core novelty (R3); cheap, high leverage.
3. **Bootstrap CIs over runs/sequences for AURC & overconf@ret (P2-4)** — makes the small CARLA margin (+0.009) and
   the "beats baselines" claims statistically defensible (R1, R5). Cheap, directly answers the most severe attacks.

> (Honorable mention: reframing the cv_smoothing result as *supporting* the temporal-consistency thesis is a
> writing task, not an experiment — do it regardless; it converts the biggest weakness into evidence.)

---

## One-paragraph honest bottom line
Paper-2 is now **conference-ready in structure and defenses** (baselines, leakage, calibration, threshold
robustness, planner probe all done and honest), with **two real blockers** (stereo KITTI, Qiu table) before it is
journal-grade. The headline is a genuine, well-evaluated **selective-prediction** contribution that wins in-domain
and under calibration; the honest caveat — a constant-velocity-residual gate wins on direct transfer — actually
reinforces the temporal-consistency thesis if framed correctly. Lead with KITTI in-domain + mixed-train, disclose
transfer weakness, add CIs, finish stereo + Qiu table.
