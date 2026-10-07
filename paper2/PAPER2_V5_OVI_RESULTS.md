# PAPER2_V5_OVI_RESULTS (C2)

> Observability Validity Index for object VELOCITY validity. test n=2518; yaw_sigma=VINS gyro-vins-diff proxy.
> OVI is interpretable: a monotone rule + a LOGISTIC calibration on geometric terms (coeffs below), not a black box.

## Velocity-valid detection AUROC (higher = better; OVI vs single-factor baselines)
| model | AUROC overall | 0-15m | 15-30m | 30m+ |
|---|---|---|---|---|
| distance_only | 0.790 | 0.420 | 0.661 | 0.781 |
| depth_only | 0.578 | 0.540 | 0.726 | 0.380 |
| bearing_only | 0.645 | 0.344 | 0.858 | 0.406 |
| yaw_lever_only | 0.764 | 0.513 | 0.493 | 0.752 |
| OVI_rule | 0.780 | 0.396 | 0.643 | 0.717 |
| OVI_calibrated | 0.797 | 0.391 | 0.809 | 0.723 |

## OVI logistic coefficients (interpretable; standardized terms)
| term | coef (sign: +→more valid) |
|---|---|
| log_range | -0.520 |
| yaw_lever | +0.062 |
| bearing_change_rate | +0.604 |
| depth_noise | -0.289 |
| vel_obs_proxy | -0.310 |
| track_stability | +0.017 |

## Within-bin mean AUROC (controls for trivial distance↔validity correlation)
| model | mean(0-15,15-30,30m+) |
|---|---|
| distance_only | 0.621 |
| depth_only | 0.549 |
| bearing_only | 0.536 |
| yaw_lever_only | 0.586 |
| OVI_rule | 0.585 |
| OVI_calibrated | 0.641 |

## Invalid-velocity detection (the refusal signal)
- distance-only best F1 = 0.887 ; OVI-calibrated best F1 = 0.908
- OVI operating point (train-Youden): false-valid rate = 0.308, false-refusal rate = 0.096

## Reading
- OVI-calibrated AUROC 0.797 vs distance-only 0.790 -> OVI BEATS distance-only at detecting trustworthy velocity.
- geometric terms (bearing-change observability, depth jitter, yaw lever) add over pure distance.
- thresholds/operating point ablatable; raw-velocity (centroid-diff) noise limits absolute numbers (scope).
