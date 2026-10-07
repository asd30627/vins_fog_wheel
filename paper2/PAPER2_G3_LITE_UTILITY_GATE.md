# PAPER2_G3_LITE_UTILITY_GATE

> OFFLINE localization-feedback utility-gate analysis over NOUE-object test preds (n=3109). NO backend change, NO object factor, NO ATE claim.

## Feedback-candidate gate
- primary gate (percentile): pred_sigma<=p10 AND p_observability>0.5 AND p_invalid_vel<=0.5
- strict absolute gate (p_obs>0.7 AND sigma<q33 AND pred_pos_err<2m AND not-invalid) -> 0 candidates (0 = conservative do-no-harm: object-only NOUE never confident enough for absolute feedback)

| group | count | frac | actual pos_err med | actual pos_err p95 |
|---|---|---|---|---|
| feedback candidates | 1 | 0.000 | 2.45 | 2.45 |
| non-candidates | 3108 | 1.000 | 3.15 | 108.50 |

## Do-no-harm proxy
- candidates' actual pos_err median 2.45 m vs non-candidates 3.15 m — gate IS selecting lower-error objects.
- NOUE uncertainty AUROC for high-error (>3m): 0.622.
- pseudo object-factor candidate log -> paper2_g3_feedback_candidates.csv (1 rows).

## G3 backend scaffold status
- A2 status = **BLOCKED**. Per spec, G3 backend object-factor scaffold proceeds ONLY if A2=promising.
- A2 is BLOCKED tonight (VINS-quality conditioning needs VINS replay) -> **G3 backend scaffold HELD** (no new branch, no estimator edit). Only this offline utility-gate analysis was done.
- When A2 is unblocked & promising: create branch `paper2-g3-object-factor-scaffold`, object factor default OFF, baseline bit-identical when OFF, compile-check only, no ATE claim.
