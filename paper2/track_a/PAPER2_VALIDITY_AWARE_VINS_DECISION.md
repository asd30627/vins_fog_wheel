# PAPER2 Part 2 — VALIDITY-AWARE VINS DECISION (honest)

> Evidence: `PAPER2_VINS_DATASET_AUDIT.md` (A), `PAPER2_VINS_BASELINE_RESULTS.md` (B),
> `PAPER2_VALIDITY_AWARE_VINS_RESULTS.md` + `paper2_validity_aware_vins_metrics.csv` (C).
> True stereo-inertial VINS on CARLA, offline (CARLA OFF), GT only for eval/oracle. 4 runs × 4 variants.
> Intervention = LEFT-image feature suppression of dynamic-object bboxes (no BA/backend edit). Date 2026-07-01.

Headline numbers (mean ATE_rmse vs baseline, 4 runs): all_dynamic **−9.2%**, validity_aware **−11.0%**,
oracle **−16.8%**; 0 VINS failures anywhere. On the 2 STABLE-baseline runs all variants cluster at ~**−6%**.

---

## The 8 questions

### 1. Can Paper-2 validity/refusal improve VINS/VIO?
**Yes, modestly and conditionally — concept validated, not yet a robust win.** Suppressing dynamic-object
image features improves Umeyama ATE on average (oracle −16.8%, deployable −9 to −11%) with **zero added VINS
failures**, and a consistent ~6% on stable baselines. So dynamic objects *do* pollute VINS and removing them
*does* help. BUT the gain is small on well-behaved runs and **erratic on degraded baselines** (on Town07 the
deployable mask makes ATE 21–29% WORSE; only the GT oracle still helps). It is a real effect, not a robust
deployable improvement.

### 2. per-frame or sequence model better for feeding back into VINS?
**Per-frame** — confirmed by both Part 1 (sequence edge insignificant on CARLA) and Part 2 (the masking
decision is per-detection-per-frame; a track-window buffer adds latency for no measured VIO benefit). The
deployable signal we actually used is the per-frame raw-speed gate; the Part-1 per-frame TCSV model is the
drop-in learned upgrade.

### 3. What was most effective: removal / soft-weight / routing / object-factor / learning-through-BA / nothing?
**Feature removal (input suppression)** was the only mechanism tested and it is the right first rung: it
needs no backend edit and already exposes the effect. Soft weighting / covariance scaling / object factors /
learning-through-BA were **not** run — gated by the result: since even *oracle* removal only buys −16.8% and
deployable removal is unreliable, the expected payoff of the much more invasive BA-level methods does not yet
justify them. Honest ranking on evidence: oracle-removal > deployable-removal ≈ all-dynamic-removal > (untested).

### 4. Is it necessary to push the loss through BA?
**No — not now.** Frozen per-frame validity → input feature suppression already realizes the available signal
on stable runs. Differentiable/through-BA learning is not warranted while (a) the dominant error is IMU
scale-drift, not dynamic pollution, and (b) deployable removal isn't reliably beating baseline. (Also gated
by the user: don't force differentiable BA when the baseline isn't rock-solid.)

### 5. If frozen validity + factor weighting already works, can we skip end-to-end BA?
**Yes.** Frozen validity + input-level suppression is sufficient to demonstrate and (on stable runs) realize
the benefit. End-to-end BA is unjustified at this evidence level.

### 6. If no improvement, should Paper-2 stay planner-facing and not claim localization improvement?
**Largely yes — claim carefully.** The defensible localization claim is narrow: *"selectively suppressing
features on dynamic objects yields a small ATE improvement on stable VIO and never increases failures, with a
deployable validity gate matching naive all-dynamic removal; perfect (oracle) routing gives the upper bound
(~−17%)."* We should **NOT** claim a robust, general VIO improvement — it can hurt on degraded baselines. The
stronger, safer Paper-2 story remains **planner/perception-facing selective validity** (Part 1), with the VINS
result as a **bounded, honest secondary finding**, not the headline.

### 7. Can this be a Paper-2 extension, or a separate Paper-3?
**Separate Paper-3 (or a major extension), not part of core Paper-2.** A credible localization paper needs to
(a) fix/curb the scale-drift baseline so dynamic pollution is the leading error, (b) show the deployable
validity gate *reliably* ≥ all-dynamic and ≈ oracle across many stable sequences, and (c) likely move from
input-masking to soft covariance weighting / a dynamic-object factor. That is a full additional program.

### 8. Does this line fit the 國科會 GPS-denied / mapless navigation theme?
**Yes, directly.** Robust VIO under dynamic traffic with no GPS/HD-map is squarely GPS-denied mapless
navigation. The honest, bounded result (validity-aware feature handling helps stable VIO; oracle bounds the
gain) is a legitimate contribution to that theme — provided it is scoped honestly and paired with the
scale-drift caveat.

---

## What would change the verdict (next steps, not done tonight)
1. **Curb baseline scale-drift** (IMU noise/extrinsic/td tuning, or wheel/FOG which we deliberately excluded)
   so dynamic-object pollution becomes the leading error → larger, cleaner masking gains.
2. **Plug the Part-1 learned TCSV model** in place of the raw-speed gate for `validity_aware`; test whether a
   better validity signal makes selective reliably beat all-dynamic (tonight it did not).
3. **Scale to many stable sequences** with bootstrap CIs (4 runs, high variance, is not enough to conclude).
4. **Add a stability gate**: only apply suppression when the VIO state is healthy (avoids the Town07-style
   regressions where masking a degraded baseline hurts).
5. If 1–4 hold, escalate from input-masking to **soft covariance weighting / dynamic-object factor**.

## One-paragraph verdict
Validity-aware dynamic-object feature suppression is a **real but modest and not-yet-robust** lever on VINS:
it improves ATE on stable baselines (~6%, oracle upper bound −17%) and never increases failures, but the
deployable signal only matches naive all-dynamic removal and can hurt when the baseline is already degraded.
The dominant VIO error here is IMU scale-drift, not dynamic pollution. **Recommendation: keep Paper-2's
headline planner/perception-facing (Part 1); report this VIO result as a bounded, honest secondary finding;
spin the full localization story into a separate Paper-3 only after curbing scale-drift and proving the
deployable gate reliably approaches oracle.**
