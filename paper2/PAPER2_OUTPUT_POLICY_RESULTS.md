# PAPER2_OUTPUT_POLICY_RESULTS

> Uncertainty-driven output policy over NOUE-object test predictions (n=3109).

## Level distribution
| level | count | frac |
|---|---|---|
| full_state | 465 | 0.150 |
| high_covariance | 215 | 0.069 |
| position_only | 2118 | 0.681 |
| conservative_warning | 311 | 0.100 |

## Effect
| metric | value |
|---|---|
| overconfident-wrong-speed (policy: among vel-emitters that are truly invalid) | 0.387 |
| overconfident-wrong-speed (no policy: all emit velocity) | 0.586 |
| invalid-velocity recall (withheld / true-invalid) | 0.856 |
| invalid-velocity precision (true-invalid / withheld) | 0.641 |
| planner-usable object ratio | 0.900 |
| risk-coverage mean pos_err @80% (low-sigma) | 25.10 |
| mean pos_err @100% (all) | 29.02 |

## Reading
- policy REDUCES overconfident wrong-velocity (0.586 -> 0.387 among emitters).
- risk-coverage: keeping the 80% lowest-uncertainty cuts mean pos_err 29.02 -> 25.10 m.
- thresholds = sigma q66/q90 + p_invalid_vel>0.5 (documented; not tuned).
- NOTE: NOUE here is object-only (VINS-quality conditioning blocked); policy quality bounded accordingly.
