# PAPER2_V5_REFUSAL_POLICY_RESULTS (C3)

> Refusal-aware object state policy on test n=2518. Velocity emitted ONLY in full_state.
> OVI thresholds (train-Youden): vel 0.130, pos 0.415.

## Policy comparison
| policy | emit_velocity_frac | overconfident_wrong_velocity | invalid_recall | valid_retention | false_refusal |
|---|---|---|---|---|---|
| no_policy | 1.000 | 0.839 | 0.000 | 1.000 | 0.000 |
| distance_policy(range<15) | 0.367 | 0.636 | 0.722 | 0.830 | 0.170 |
| v5_OVI_policy | 0.403 | 0.640 | 0.692 | 0.904 | 0.096 |

## v5 OVI policy level distribution (test)
| level | count | frac |
|---|---|---|
| full_state | 1016 | 0.403 |
| position_only | 961 | 0.382 |
| conservative_warning | 48 | 0.019 |
| unobservable | 493 | 0.196 |

- planner-usable (full_state OR position_only) ratio = 0.785

## Overconfident-wrong-velocity by distance bin (no-policy → OVI policy)
| bin | no_policy | v5_OVI |
|---|---|---|
| 0-15m | 0.516 | 0.504 |
| 15-30m | 0.914 | 0.727 |
| 30m+ | 0.950 | 0.863 |

## Reading
- v5 OVI policy cuts overconfident-wrong-velocity 0.839 → 0.640 among emitted, at false-refusal 0.096 (invalid-velocity recall 0.692).
- vs naive distance<15 policy (overconf 0.636, false-refusal 0.170).
- reference: v4 NOUE policy reported overconfident 0.586→0.387 on its own split (PAPER2_OUTPUT_POLICY_RESULTS.md; different split, not directly comparable).
- thresholds/operating point ablatable; position_only is a real regime (position usable, velocity withheld).
