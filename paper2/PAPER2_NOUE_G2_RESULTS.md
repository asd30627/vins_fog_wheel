# PAPER2_NOUE_G2_RESULTS — Phase G2 (run 20260630_042852)

> dataset n=15811 (train 11432/val 1270/test 3109); feats=27 (object-only).
> **A2 (VINS-quality conditioning) = BLOCKED** — no reliability_features_vins.csv for these recordings (needs VINS replay). Not fabricated.
> Achievable G2 comparison tonight: distance-only vs geometry-gate vs NOUE-object (learned, all object features).

## Test metrics (pos-error prediction + calibration)
| model | rmse | med_abs | p95_abs | NLL | calib_err | AUROC_high | riskcov_err@80 | overconf_wrong |
|---|---|---|---|---|---|---|---|---|
| distance_only | 47.40 | 2.47 | 105.90 | 5.241 | 0.087 | 0.466 | 27.66 | 0.396 |
| geometry_gate | 47.41 | 4.05 | 105.86 | 584.154 | 0.148 | 0.494 | 31.01 | 0.564 |
| noue_object | 44.20 | 5.01 | 101.82 | 20.522 | 0.136 | 0.622 | 24.10 | 0.453 |
| h1_residual_refine | 45.57 | 4.52 | 103.22 | 5.296 | 0.114 | 0.500 | 26.45 | 0.000 |

## NOUE-object per distance bin
| bin | n_metric | rmse | NLL | AUROC_high | overconf_wrong |
|---|---|---|---|---|---|
| 0-15m | - | 51.98 | 13.994 | 0.748 | 0.348 |
| 15-30m | - | 48.67 | 35.020 | 0.393 | 0.619 |
| 30m+ | - | 27.06 | 11.063 | 0.675 | 0.385 |

## NOUE-object binary heads (AUROC)
- invalid_velocity: 0.6548102963698192
- observability: 0.7588707504983567
- utility: 0.6504710599342294

## H1 isolated ablation
- H1 = point-estimate residual refine (NO calibrated uncertainty); reused constant sigma for metrics.
- H1 rmse=45.57 vs NOUE-object rmse=44.20.
- Interpretation: if H1 rmse < NOUE rmse but calib_err/NLL worse, it trades calibration for point accuracy (keep isolated).

## A2 status
- **BLOCKED** — no reliability_features_vins.csv for these CARLA recordings (needs VINS replay); per G0 spec, VINS-conditioned marked blocked, not fabricated
- Achievable proxy verdict (NOUE-object vs distance-only/geometry): NOUE-object does NOT clearly beat baselines on NLL+AUROC (object features alone limited).

## Honest caveats
- A2's核心 (VINS-quality conditioning) NOT tested tonight — blocked on VINS replay.
- small/medium dataset; group-split by run; metrics noisy if test small.
- labels use fixed thresholds (pos>3m, spd>3, invalid spd>5 or dir>45) — choices, documented in builder.
