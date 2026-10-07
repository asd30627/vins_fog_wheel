# PAPER2_V5_VALIDITY_LABEL_REPORT (C1)

> Dynamic-object state validity labels from 15811 GT-matched detections (15459 have a raw velocity estimate). Thresholds are CHOICES (ablatable), not truth.

## Thresholds (ablatable)
- position_valid: pos_err<= 3.0 m ; velocity_valid: speed_err<= 3.0 m/s AND dir_err<= 45.0°
- unobservable_candidate: invalid_velocity AND (|bearing_change|<0.5°/frame OR range>30.0 m OR depth_jitter>0.3)
- high_risk_object: invalid_velocity AND range<15.0 m

## Overall label rates
| label | rate |
|---|---|
| pos_valid | 0.485 |
| vel_valid | 0.127 |
| full | 0.089 |
| pos_only | 0.396 |
| invalid_vel | 0.873 |
| unobs | 0.821 |
| high_risk | 0.073 |

## By distance bin
| bin | n | pos_valid | vel_valid | full | position_only | invalid_vel | unobservable | high_risk |
|---|---|---|---|---|---|---|---|---|
| 0-15m | 1863 | 0.89 | 0.38 | 0.35 | 0.54 | 0.62 | 0.42 | 0.62 |
| 15-30m | 4164 | 0.73 | 0.16 | 0.13 | 0.60 | 0.84 | 0.73 | 0.00 |
| 30m+ | 9784 | 0.30 | 0.06 | 0.02 | 0.28 | 0.94 | 0.94 | 0.00 |

## By density
| density | n | vel_valid | position_only | invalid_vel |
|---|---|---|---|---|
| sparse | 1748 | 0.07 | 0.40 | 0.93 |
| medium | 4931 | 0.13 | 0.45 | 0.87 |
| dense | 9132 | 0.14 | 0.37 | 0.86 |

## By town
| town | n | vel_valid | position_only | invalid_vel |
|---|---|---|---|---|
| Town01 | 7023 | 0.12 | 0.49 | 0.88 |
| Town10HD | 8788 | 0.13 | 0.32 | 0.87 |

## Reading (C1 observability/validity regimes emerge from data)
- velocity validity collapses with range (vel_valid 0.38 -> 0.06) -> 'always output velocity' is wrong.
- position validity degrades more slowly -> 'position_only' is a real, useful regime.
- far/low-bearing-change/high-jitter -> unobservable_candidate; near+invalid -> high_risk.
- thresholds ablatable; absolute rates depend on raw-velocity (centroid-diff) noise — scope honestly.
