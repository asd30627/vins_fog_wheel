# PAPER2 — TCSV × VINS ROBUST-LOSS DECISION (INTERIM, pre-run)

> Status = **GATED at Phase-2 experiments**. The audit + plan + switch + scoring are done; the 8×2
> ablation has NOT been run (needs binary rebuild + bbox→feature builder + CARLA-stopped replay).
> This doc answers what is answerable from the source audit NOW and marks the rest GATED-pending-runs,
> so no result is fabricated. Date 2026-07-01.

## Answers to the 9 questions

1. **How big is VINS's own robust loss / Huber?** — **ANSWERED (smoke, Town01 dense_b1).**
   Huber's standalone protective value on this clean run is **~zero, mildly negative**: turning it off
   (`REL_VISUAL_ROBUST_LOSS=0`) did NOT diverge (0 fail, 269 poses) and ATE slightly *improved*
   3.35 → 2.86 m. The **backend 3-px cull is the real robustness layer and is ~Huber-independent**: mean
   outlier_ratio 0.518 (Huber on) vs 0.505 (off) — same ~51% culled either way. So the dominant
   confounder is the 3-px cull, NOT Huber. (n=1 run, single seed; late-scale ≈0.5 both → don't over-claim
   the −15%. Directionally solid; V2 on medium_b1 pending.) Full table: `PAPER2_TCSV_HUBER_ABLATION_RESULTS.md`.

2. **Does TCSV-M still improve with Huber ON?** — **GATED (V6 vs V1).** Not yet run. Prior signal was
   raw_speed_gate (not TCSV-M) and only −10.5%/−2.8% ATE on these 2 runs — inside the noise of "removing
   dynamic features at all". Unproven for the real model.

3. **Is TCSV-M > raw_speed_gate?** — **GATED (V5/V6 vs V4).** Not yet run.

4. **Is TCSV-M ≥ all_dynamic?** — **GATED (V5/V6 vs V3).** Prior clean-run evidence had
   deployable ≈ all_dynamic ≈ oracle (within ~1%), i.e. no sophistication advantage demonstrated. Must
   re-test with real TCSV-M.

5. **Soft > hard (more stable)?** — **GATED (V6 vs V5).** Not yet run. Mechanistically, soft avoids the
   discrete feature-count cliff of hard masking, but soft couples with Huber multiplicatively (see below).

6. **Can TCSV-M partly replace Huber (Huber off)?** — **GATED (V7 vs V2).** Not yet run; V2/V7 are the
   smoke-test-gated cells (Huber-off may diverge).

7. **TCSV-M vs Huber: complement / overlap / interfere?** — **PARTIALLY ANSWERABLE now, sign GATED.**
   *Mechanism is proven* (`PAPER2_TCSV_SOFT_WEIGHTING_HUBER_INTERACTION.md`): TCSV weight enters as
   `feat_weight_` **before** Huber, so Huber re-thresholds the weighted residual — they are
   **multiplicatively coupled, not additive**. A small TCSV weight both cuts leverage AND un-saturates the
   feature from Huber's robust arm (partially opposing effects). The empirical sign
   `(V6−V1) − (V7−V2)` is GATED.

8. **Can we claim "TCSV-M improves VINS localization in dynamic scenes"?** — **NO.** Not now, and not
   from the current evidence base: (a) the de-confounding 2×2 has not been run; (b) even the prior
   positive signal is n=2 clean runs, raw_speed_gate not TCSV, and ≈ all_dynamic ≈ oracle; (c) the
   dominant error on these runs is IMU scale-drift, and the dominant feature-cleaner is the 3-px cull,
   not the method. Claiming localization improvement would over-reach.

9. **What CAN we claim?** — **Only object-state validity**, per `PAPER2_VINS_LOCALIZATION_CONTRIBUTION_DECISION.md`:
   > "We can claim a learned per-object validity signal (TCSV-M) that routes detections by
   > position/velocity trustworthiness. We CANNOT yet claim a VINS/VIO **localization** improvement:
   > the effect is unproven against the estimator's pre-existing Huber + 3-px outlier rejection, tested
   > on too few clean runs, and confounded by IMU scale-drift."
   The VINS line stays a **bounded appendix / future-Paper-3** item until the gated 2×2 runs land.

## What is DONE (this phase)
- `PAPER2_VINS_ROBUST_LOSS_AUDIT.md` — every robust mechanism located in source.
- `PAPER2_TCSV_HUBER_ABLATION_PLAN.md` — the 8×2 de-confounding matrix + smoke-test gate.
- `PAPER2_TCSV_SOFT_WEIGHTING_HUBER_INTERACTION.md` — weight-before-Huber proven from the factor code.
- `REL_VISUAL_ROBUST_LOSS=1/0` implemented in `estimator.cpp` (visual-only; IMU/marg/wheel untouched).
- `scripts/paper2_vins_tcsv_masking.py` + `paper2/track_a/paper2_tcsv_vins_scores.csv` — real
  TCSV-M(mono), leak-free per-detection scores + routing policy (NOT raw_speed_gate).

## The remaining GATE (what Phase-2 runs need, in order)
1. `colcon build` the estimator with the switch (binary not yet rebuilt).
2. Build the **bbox→VINS-feature** router (map `feat_weight` per bbox to `feat_weight_` / to a hard drop) —
   the one piece that turns per-object scores into per-feature routing. Reuse
   `paper2_carla_stereo_player_masked.py` / `paper2_make_vins_masks.py`.
3. **V1** reproduce baseline; **V2 smoke** (Huber off, no routing, Town01 dense only) — if it diverges,
   record the failure, do not force the full Huber-off sweep.
4. Full V3–V8 on Town01 dense_b1 + medium_b1 ONLY, CARLA stopped, b05+rate0.5+skip-imu-head150.
5. Emit `paper2_tcsv_huber_ablation_metrics.csv` + `PAPER2_TCSV_HUBER_ABLATION_RESULTS.md`, then finalize
   this decision with real numbers.

**STOP here for裁示** before spending the rebuild + replay budget.
