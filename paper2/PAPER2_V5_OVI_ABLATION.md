# PAPER2_V5_OVI_ABLATION (C2 — is the geometry real or just distance?)

> Velocity-valid detection AUROC, leave-one-term-out on the OVI logistic. test n=2518.

## Leave-one-term-out (drop_X delta < 0 ⇒ term X helped)
| model | AUROC | Δ |
|---|---|---|
| OVI_full | 0.797 | +0.008 |
| drop_yaw_lever | 0.796 | -0.001 |
| drop_bearing_change_rate | 0.794 | -0.003 |
| drop_depth_noise | 0.795 | -0.002 |
| drop_vel_obs_proxy | 0.798 | +0.001 |
| drop_track_stability | 0.797 | -0.001 |
| distance_only(log_range) | 0.790 | +0.000 |

## OVI vs distance-only per distance bin
| bin | OVI | distance-only | Δ |
|---|---|---|---|
| 0-15m | 0.391 | 0.420 | -0.030 |
| 15-30m | 0.809 | 0.661 | +0.148 |
| 30m+ | 0.723 | 0.781 | -0.058 |

## Low-bearing-change stratum (velocity geometrically weakly observable)
- velocity_valid rate: low-bearing-change 0.128 vs high 0.189 → geometry predicts velocity unobservable when bearing barely changes.
- OVI AUROC 0.883 vs distance-only 0.885 in this stratum (Δ -0.002).

## Honest reading
- OVI overall AUROC 0.797 vs distance-only 0.790 (Δ +0.008) — a real but MODEST geometric gain over pure distance.
- the term that helps most = the one whose drop_X is most negative (see table); bearing-change-based velocity observability is the expected key non-distance term.
- OVI is positioned as an INTERPRETABLE auxiliary index, NOT the sole contribution; if the gain is modest we say modest (it is).
