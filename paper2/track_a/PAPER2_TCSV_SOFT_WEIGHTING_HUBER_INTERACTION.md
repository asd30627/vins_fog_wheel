# PAPER2 — TCSV SOFT WEIGHTING × HUBER INTERACTION

> Exactly how a TCSV per-feature weight w_i combines with the visual Huber in this VINS, proven
> from the factor source, not assumed. Answers: is `weighted_residual = w_i·r` the whole story? (No.)
> Date 2026-07-01.

---

## 1. Where the weight is applied — from source

In every projection factor's `Evaluate()` (mono `projectionTwoFrameOneCamFactor.cpp:76-81`, and the two
stereo factors identically):

```cpp
if (use_inst_sqrt_info_) {
    residual = sqrt_info_inst_ * residual;   // anisotropic whitener W (Route C)
} else {
    residual = sqrt_info * residual;         // isotropic whiten (FOCAL_LENGTH/1.5)
    residual *= feat_weight_;                // <-- TCSV weight w_i, DEFAULT 1.0
}
```

and the Jacobian is scaled the same way (`reduce *= feat_weight_`, line 108). So the cost function
returns to Ceres:

```
r_i(x) = w_i · W · reproj_i(x)          (W = sqrt_info)
```

**The weight is applied INSIDE the cost function, BEFORE Ceres hands the residual to the loss.**

## 2. Order: weight first, Huber second — NOT the reverse

Ceres computes the per-block contribution as `ρ( ‖r_i‖² )`, where `ρ` is the Huber loss and `r_i` is
what the cost function returned. Because `r_i = w_i·W·reproj`:

```
cost_i = ρ_Huber( ‖ w_i · W · reproj_i ‖² ) ,   ρ_Huber(s²)= s²            if ‖·‖ ≤ δ
                                                            = 2δ‖·‖ − δ²   if ‖·‖ > δ   (δ=1.0)
```

So the answer to the user's three sub-questions:

1. **residual × w_i then Huber?** → **YES.** `residual *= feat_weight_` runs inside `Evaluate()`; Huber sees the already-weighted residual.
2. **Huber then × weight?** → **NO.** There is no post-loss scaling; the loss is the last thing Ceres applies.
3. **Does the order change Huber's effective threshold?** → **YES, exactly as feared.** Huber's kink is at `‖w_i·W·reproj‖ = δ`, i.e. at `‖W·reproj‖ = δ / w_i`. A small w_i **raises** the reproj level needed to enter Huber's robust (linear) arm — the feature is pulled *toward* the quadratic/inlier arm and is trusted more per unit residual, but with smaller overall leverage. TCSV weight and Huber are **coupled multiplicatively through the argument of ρ**, not additive and not independent.

### Consequence for interpretation
- **Down-weighting a dynamic feature (small w_i) does two things at once:** (a) shrinks its Jacobian leverage (the intended effect), and (b) moves it out of Huber saturation so Huber stops discounting it. Effect (b) partially *opposes* (a). This is why "TCSV soft weighting on top of Huber" can look weaker than expected — Huber was already saturating exactly those features, and TCSV both removes leverage and un-saturates them.
- **The clean way to see TCSV's own contribution is with Huber OFF** (variant V7 vs V2 in the ablation plan): then `cost_i = ‖w_i·W·reproj‖²`, weight acts purely as a variance re-scaling with no threshold coupling.

## 3. Huber saturation ratio — definition + how to record

**Definition.** Fraction of *active* visual residual blocks whose whitened norm exceeds δ:
```
sat_ratio = #{ i : ‖ w_i · W · reproj_i(x*) ‖ > δ } / #visual_blocks     (δ = REL_HUBER_DELTA = 1.0)
```
Interpretation: how much of the visual channel Huber is actively discounting. If TCSV soft weighting is
doing real work *of the same kind as Huber*, `sat_ratio` should **drop** when TCSV is on (fewer features
in the robust arm) — and any ATE gain over V1 is then "more than Huber already gave".

**How to record (not yet instrumented — small add):** in `optimization()` after `ceres::Solve`, loop the
stored visual `ResidualBlockId`s (`dbg_mono_ids` / `dbg_stereo_ids` already collected, `estimator.cpp:2478`),
call `problem.EvaluateResidualBlock(id, /*apply_loss=*/false, &cost, res, nullptr)` to get the raw
`r_i = w_i·W·reproj`, and count `‖r_i‖ > δ`. Log as a new column `huber_saturation_ratio`. ~15 lines,
read-only, gated behind an env flag (e.g. `REL_LOG_HUBER_SAT=1`) so the gate binary is untouched.

**Fallback if not instrumented** (the user's requested minimum): record per variant
`outlier_ratio_last` (3-px cull fraction), `reproj/opt cost` (Ceres `final_cost`, add one log line),
`tracked_feature_count_mgr`. `outlier_ratio_last` is a coarse proxy for saturation (both track
high-reproj features), but it is the *hard* 3-px cull, not the *soft* Huber arm — report them as
distinct signals.

## 4. What this means for the claim

- A naive `weighted_residual = w_i·r` narrative is **insufficient and slightly wrong** for this codebase: it omits that Huber then re-thresholds the weighted residual. Any paper text must state the order (weight-before-loss) and the threshold-coupling.
- The decisive evidence that "TCSV soft weighting is not just Huber" is the **2×2** (V1/V2/V6/V7): TCSV must move ATE **in the Huber-off column too** (V7 vs V2), and the sign of the interaction `(V6−V1) − (V7−V2)` tells us complementary (both same sign, additive), redundant (V6≈V1 while V7<V2), or interfering (opposite signs).
- Until that 2×2 is run on the clean runs, we can only say TCSV *feeds the existing R3 slot*; we cannot say it improves localization independently of Huber.

## 5. Note on the anisotropic path

If `use_inst_sqrt_info_` is set (Route-C per-feature 2×2 whitener), it **replaces** `sqrt_info·feat_weight_`
entirely (`residual = sqrt_info_inst_ * residual`), and the same Huber-after-whitening coupling holds with
`W = sqrt_info_inst_`. For the TCSV deployment we use the **scalar `feat_weight_` path** (isotropic W ×
scalar w_i) unless we explicitly build an anisotropic TCSV whitener — keep them separate in the ablation.
