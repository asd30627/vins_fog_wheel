# Task 2.1 — Grade-Conditioned Arbitration Network: DESIGN CHECKPOINT (for user sign-off)

> **REVISED 2026-06-26** per the user's design-revision instructions (developed with the web client). The **canonical resolved design now lives in `design.md` Decision 2 + the delta spec**; this file is the working checkpoint. Key revisions folded in: (1) six well-posedness checks added; (2) **primary multi-grade data = Allan-injection onto REAL KAIST** (Decision 3), CARLA → corroboration; (3) teacher switched from the flat **BA-oracle → direct who's-right-vs-GT label**; (4) **abstain (α≡1) outside the identifiable window** → do-no-harm ≈ free; (5) **low-capacity monotone schedule**; (6) sign-off **gated behind Probe B (oracle ceiling) then Probe A (label learnability)** — tasks 1.4/1.5. The C-section below records the original options; the revised resolution supersedes approach-A as the primary teacher.
>
> Per Decision 2 + task 2.1: network I/O, training target, GT source presented for sign-off **BEFORE any implementation** (avoiding the visual-covariance route's "built before thinking it through" failure). Nothing in `estimator.cpp` touched until sign-off AND Probes B/A report. Drafted 2026-06-26, informed by the autonomous 30s baseline + grade sweep findings (`AUTONOMOUS_RESULTS.md`).

## A. LOCKED (from design.md — recap, not up for change)
- AI acts **only** on the FOG-yaw / IMU-factor **information weight** (NULL-loss path). Never emits a visual-feature weight; never touches `ProjectionFactor`s / Huber (Anchor 2).
- **Rotation-only** scope. FOG measures rotation; "strengthen FOG = weaken vision's relative rotation say" bypasses Huber. Translation still relies on vision+IMU+wheel (stated limitation).
- Discrete grades; env-gated default-OFF (flag-OFF bit-identical); LOSO eval; per-segment Pit-1 health gate.

## B. NEW FINDINGS THAT RESHAPE THIS DESIGN (from autonomous session)
1. **★Grade has ~no effect on 30 s sequences★** — gyro bias/ARW need TIME to integrate (precision_mems 5°/hr × 30 s = 0.04°, negligible). per-grade 30 s pass-rate was non-monotonic (4/2/3/5 of 8). **→ Training/eval data MUST be long (≥5 min); the grade signal only exists where the gyro integrates.** This directly sets the data regime for tasks 1/4.
2. **The 30 s init-success baseline is route/town-dominated, grade-invariant** (Town10HD 88%, Town04 0%). So the AI's value is NOT 30 s scale pass/fail; it is **long-horizon rotation drift** (where grade bites).
3. **Failure mechanism (translation/scale):** wheel forward residual escapes → Huber saturates the *wheel* constraint → scale drifts. This is a **translation** failure → **outside** the rotation-only FOG-arbitration scope (honest: the AI won't fix Town04-type scale drift; that's a separate lever). Keeps scope clean.

## C. OPEN DECISIONS — my recommendation, for your sign-off / adjust

### D2a — Network INPUTS
- **(i) FOG grade indicator** — the Allan parameters of the active grade: `[ARW, bias_instability, BRW]` (3 numbers), normalized. (Not one-hot → generalizes between discrete points, supports the KAIST-0.05 alignment point.)
- **(ii) Scene-dynamics signal** — **must be RUNTIME-observable** (KAIST deploy has no GT). Recommend a VIO-internal proxy, candidates:
  - `v_dyn1` = fraction of tracked features flagged outlier / high reprojection residual per keyframe (proxy for moving-object corruption);
  - `v_dyn2` = visual-vs-IMU rotation disagreement (per-keyframe gyro-integrated ΔR vs visual ΔR residual).
  - **Recommend v_dyn2** (directly measures "is vision's rotation trustworthy now"), with v_dyn1 as a fallback feature. For TRAINING we can additionally use CARLA GT dynamic-object coverage to validate the proxy, but the deployed input is proxy-only.
- ❓**Sign-off:** grade = Allan-3 vector? dynamics proxy = v_dyn2? include v_dyn1?

### D2b — Network OUTPUT
- A scalar **arbitration coefficient α ∈ [α_min, α_max]** multiplying the **FOG-yaw factor information** (inverse-covariance) per keyframe. α↑ = trust FOG rotation more (→ vision's relative rotation say ↓, no Huber touched). Bounded so flag-OFF (α≡1) is the bit-identical baseline.
- ❓**Sign-off:** single scalar α on FOG-yaw information? bounds (e.g. [0.25, 4])?

### D2c — TRAINING TARGET + APPROACH ★the central question★
The estimator is Ceres BA (not trivially differentiable). Three options:
- **(A) Supervised "oracle" weight (RECOMMEND as the tractable start).** Per healthy segment, grid-search the α that minimizes that segment's GT rotation error → that is the oracle label; train `f(grade, dynamics) → α*`. Pros: tractable, no BA backprop, interpretable. Cons: per-segment-optimal ≠ globally optimal; needs the grid-search data-gen pass.
- **(B) End-to-end through the estimator.** Differentiate ATE/rotation-error back to α. Needs a differentiable BA surrogate — high effort/risk.
- **(C) Black-box / finite-difference reward.** Network outputs α; downstream ATE is the reward; optimize by finite-diff/CMA-ES/RL. No differentiability needed but expensive (many BA runs/step).
- **Target metric:** per-segment **rotation error** (relative, since rotation is the scope) — NOT full ATE (translation is out of scope).
- **GT source:** KAIST real GT pose (the only real FOG anchor, 0.05°/hr) + CARLA GT pose (mid/low grades).
- ❓**Sign-off:** approach **A** (supervised oracle)? target = per-segment rotation error?

### D2d — Sequence length regime (NEW, forced by finding B1)
- Train/eval on **≥5 min** sequences (CARLA grade matrix has 300 s + the new 5-min runs; KAIST sequences are long). 30 s is **invalid** for grade study. 120 s primary / 300 s corroboration (per Pit-1) should be **re-examined** — 120 s may already be too short for grade to integrate; the running 5-min study will tell us.
- ❓**Sign-off:** adopt ≥5 min as the grade-study regime (revisit the 120 s primary choice once the 5-min curve is in)?

## D. WHAT I WILL NOT DO until sign-off
- No `estimator.cpp` change, no network code, no training. (Task 3 is gated behind this sign-off.)

## E. Where this sits in the task graph
- Task 1 (per-grade FOG-base baseline / Curve 1): the autonomous 30 s grade sweep is a **partial** Curve-1 (but 30 s → grade-flat, so it mainly proves the long-seq requirement). The running **5-min grade study** is the real Curve-1 data generator.
- Task 0.e (dynamic×healthy window pre-check) still pending — depends on D2a(ii) dynamics metric choice.
- This doc = task 2.1; on sign-off → task 3 implementation.
