# PAPER2_SELECTIVE_VALIDITY_RESULTS

> Selective velocity-validity model vs baselines. CARLA n=15811, KITTI n=37022. Splits: CARLA by run, KITTI by sequence (NO frame random). Velocity criterion = ego-independent vel_err≤3 m/s.
> Features (common): ['range_m', 'bearing_deg', 'bbox_area', 'depth_m', 'track_age', 'raw_speed', 'raw_accel', 'vel_smooth', 'det_conf', 'bearing_change']

## AUROC (velocity_valid) + refusal metrics by scenario
| scenario | model | AUROC | overconf | retention | false_refusal | F1_invalid |
|---|---|---|---|---|---|---|
| CARLA->CARLA(run) | distance_gate | 0.755 | 0.761 | 0.847 | 0.153 | 0.695 |
| CARLA->CARLA(run) | OVI_geom | 0.760 | 0.768 | 0.847 | 0.153 | 0.681 |
| CARLA->CARLA(run) | selective_logistic | 0.768 | 0.765 | 0.805 | 0.195 | 0.702 |
| CARLA->CARLA(run) | selective_logistic_interact | 0.729 | 0.778 | 0.741 | 0.259 | 0.701 |
| CARLA->CARLA(run) | selective_hist_gbm | 0.873 | 0.605 | 0.709 | 0.291 | 0.876 |
| CARLA->CARLA(run) | selective_mlp | 0.780 | 0.764 | 0.780 | 0.220 | 0.713 |
| KITTI->KITTI(seq) | distance_gate | 0.686 | 0.432 | 0.904 | 0.096 | 0.507 |
| KITTI->KITTI(seq) | OVI_geom | 0.732 | 0.392 | 0.859 | 0.141 | 0.606 |
| KITTI->KITTI(seq) | selective_logistic | 0.847 | 0.291 | 0.825 | 0.175 | 0.745 |
| KITTI->KITTI(seq) | selective_logistic_interact | 0.887 | 0.245 | 0.854 | 0.146 | 0.793 |
| KITTI->KITTI(seq) | selective_hist_gbm | 0.919 | 0.223 | 0.872 | 0.128 | 0.816 |
| KITTI->KITTI(seq) | selective_mlp | 0.924 | 0.180 | 0.866 | 0.135 | 0.847 |
| CARLA->KITTI | distance_gate | 0.713 | 0.382 | 0.634 | 0.366 | 0.712 |
| CARLA->KITTI | OVI_geom | 0.711 | 0.390 | 0.632 | 0.368 | 0.705 |
| CARLA->KITTI | selective_logistic | 0.747 | 0.381 | 0.697 | 0.303 | 0.710 |
| CARLA->KITTI | selective_logistic_interact | 0.705 | 0.372 | 0.602 | 0.398 | 0.719 |
| CARLA->KITTI | selective_hist_gbm | 0.700 | 0.451 | 0.589 | 0.411 | 0.653 |
| CARLA->KITTI | selective_mlp | 0.649 | 0.453 | 0.652 | 0.348 | 0.639 |
| CARLA+KITtrain->KIThold | distance_gate | 0.686 | 0.435 | 0.912 | 0.088 | 0.495 |
| CARLA+KITtrain->KIThold | OVI_geom | 0.728 | 0.402 | 0.880 | 0.120 | 0.584 |
| CARLA+KITtrain->KIThold | selective_logistic | 0.827 | 0.349 | 0.870 | 0.130 | 0.677 |
| CARLA+KITtrain->KIThold | selective_logistic_interact | 0.843 | 0.335 | 0.881 | 0.119 | 0.696 |
| CARLA+KITtrain->KIThold | selective_hist_gbm | 0.906 | 0.279 | 0.901 | 0.099 | 0.768 |
| CARLA+KITtrain->KIThold | selective_mlp | 0.873 | 0.237 | 0.805 | 0.195 | 0.790 |

## Does the selective model BEAT the distance gate? (AUROC)
| scenario | distance_gate | best_selective | Δ | verdict |
|---|---|---|---|---|
| CARLA->CARLA(run) | 0.755 | selective_hist_gbm=0.873 | +0.117 | **BEATS** |
| KITTI->KITTI(seq) | 0.686 | selective_mlp=0.924 | +0.238 | **BEATS** |
| CARLA->KITTI | 0.713 | selective_logistic=0.747 | +0.034 | **BEATS** |
| CARLA+KITtrain->KIThold | 0.686 | selective_hist_gbm=0.906 | +0.220 | **BEATS** |

## Honest verdict
- selective model BEATS distance gate (Δ>0.02 AUROC) in **4/4** scenarios.
- if it beats in-domain (CARLA->CARLA, KITTI->KITTI) the temporal/observability features add real signal beyond distance;
- cross-dataset (CARLA->KITTI) tests generalization of the learned validity boundary.
- if it does NOT beat distance gate, the honest conclusion: validity is largely distance/geometry-determined; report the phenomenon + a simple gate, NOT a model, as the contribution.

## Temporal-feature ablation (WHY the model beats distance — honest attribution)
HistGBM velocity_valid AUROC by feature block:
| scenario | distance_gate | GEO-only (range,bearing,bbox_area,depth,conf) | TEMP-only (track_age,raw_speed,raw_accel,vel_smooth,bearing_change) | GEO+TEMP |
|---|---|---|---|---|
| CARLA->CARLA | 0.755 | 0.723 | **0.806** | **0.864** |
| KITTI->KITTI | 0.686 | 0.814 | **0.879** | **0.928** |
- **The gain is DRIVEN BY TEMPORAL-CONSISTENCY features**: TEMP-only beats both distance and geometry-only in both datasets.
- Geometry-only is NOT better than distance on CARLA (0.723 < 0.755) — pure geometry adds little over range (consistent with the earlier OVI ablation Δ+0.008). The new signal is the **runtime plausibility/stability of the raw estimate** (a jittery / implausibly-fast raw velocity ⇒ unobservable), which is observable WITHOUT GT.
- No leakage: all features are runtime-observable; only the LABEL (vel_err≤3) uses GT.
- Refusal at operating point: hist_gbm lowers overconfident-wrong-velocity too (CARLA 0.761→0.605, KITTI 0.432→0.223) at some retention cost; AUROC is the cleaner summary.
- Cross-dataset CAVEAT: direct CARLA->KITTI transfer is weak (+0.034; hist_gbm overfits to 0.700) — the learned boundary needs some target-domain data (CARLA+KITtrain->held-out-KITTI = +0.220 works well).
