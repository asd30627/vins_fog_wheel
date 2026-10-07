# PAPER2_SELECTIVE_VALIDITY_RIGOROUS

> Journal-grade decision-level eval on REAL data with GT. CARLA velocity rows n=15811 (vel-valid 11.2%), KITTI n=37022 (vel-valid 43.0%). Grouped CV by run/sequence (no leakage); 5-fold x 5 repeats; 95% CI = t-interval over folds.
> GT velocity-valid criterion: ego-independent vel_err <= 3.0 m/s. Features: ['range_m', 'bearing_deg', 'bbox_area', 'depth_m', 'track_age', 'raw_speed', 'raw_accel', 'vel_smooth', 'det_conf', 'bearing_change']

## 1. Repeated grouped-CV: AUROC + refusal metrics (mean [95% CI])
| scenario | model | AUROC | overconf-wrong | retention | false-refusal | F1_inv |
|---|---|---|---|---|---|---|
| CARLA->CARLA(run) | distance_gate | 0.684 [0.645,0.723] | 0.788 [0.748,0.827] | 0.577 | 0.423 | 0.796 |
| CARLA->CARLA(run) | OVI_geom | 0.680 [0.641,0.719] | 0.792 [0.753,0.830] | 0.583 | 0.417 | 0.795 |
| CARLA->CARLA(run) | selective_logistic | 0.693 [0.654,0.731] | 0.795 [0.762,0.829] | 0.626 | 0.374 | 0.782 |
| CARLA->CARLA(run) | selective_hist_gbm | 0.814 [0.792,0.836] | 0.694 [0.658,0.730] | 0.589 | 0.411 | 0.879 |
| KITTI->KITTI(seq) | distance_gate | 0.710 [0.699,0.721] | 0.424 [0.404,0.444] | 0.693 | 0.307 | 0.676 |
| KITTI->KITTI(seq) | OVI_geom | 0.731 [0.720,0.743] | 0.403 [0.382,0.424] | 0.685 | 0.315 | 0.708 |
| KITTI->KITTI(seq) | selective_logistic | 0.854 [0.844,0.864] | 0.294 [0.278,0.310] | 0.748 | 0.252 | 0.799 |
| KITTI->KITTI(seq) | selective_hist_gbm | 0.912 [0.908,0.917] | 0.222 [0.213,0.230] | 0.811 | 0.189 | 0.848 |

## 2. Significance vs distance-gate (paired Wilcoxon on per-fold AUROC)
| scenario | model | ΔAUROC | Wilcoxon p | n_folds |
|---|---|---|---|---|
| CARLA->CARLA(run) | OVI_geom | -0.004 | 0.00056 | 25 |
| CARLA->CARLA(run) | selective_logistic | +0.008 | 0.56017 | 25 |
| CARLA->CARLA(run) | selective_hist_gbm | +0.130 | 1e-05 ✱ | 25 |
| KITTI->KITTI(seq) | OVI_geom | +0.021 | 2e-05 ✱ | 25 |
| KITTI->KITTI(seq) | selective_logistic | +0.143 | 0.0 ✱ | 25 |
| KITTI->KITTI(seq) | selective_hist_gbm | +0.202 | 0.0 ✱ | 25 |

## 3. Cross-dataset generalization CARLA→KITTI (bootstrap 95% CI over KITTI seqs)
| model | AUROC [95% CI] | overconf-wrong | retention |
|---|---|---|---|
| distance_gate | 0.713 [0.688,0.735] | 0.382 | 0.634 |
| OVI_geom | 0.711 [0.683,0.733] | 0.390 | 0.632 |
| selective_logistic | 0.747 [0.718,0.768] | 0.381 | 0.697 |
| selective_hist_gbm | 0.716 [0.679,0.755] | 0.419 | 0.544 |

## 4. Stratified AUROC (CARLA, grouped within stratum)
| stratum | model | AUROC | overconf | n |
|---|---|---|---|---|
| density=dense | distance_gate | 0.690 | 0.789 | 9132 |
| density=dense | selective_logistic | 0.707 | 0.745 | 9132 |
| density=medium | distance_gate | 0.619 | 0.764 | 4931 |
| density=medium | selective_logistic | 0.552 | 0.863 | 4931 |
| density=sparse | distance_gate | 0.592 | 0.891 | 1747 |
| density=sparse | selective_logistic | 0.376 | 0.972 | 1747 |
| town=Town01 | distance_gate | 0.671 | 0.810 | 7023 |
| town=Town01 | selective_logistic | 0.556 | 0.883 | 7023 |
| town=Town10HD | distance_gate | 0.689 | 0.809 | 8788 |
| town=Town10HD | selective_logistic | 0.744 | 0.786 | 8788 |

## 5. Threshold ablation (mean grouped-CV AUROC; ranking stability)
| VEL_T | dataset | model | AUROC |
|---|---|---|---|
| 2.0 | CARLA | distance_gate | 0.673 |
| 2.0 | CARLA | OVI_geom | 0.670 |
| 2.0 | CARLA | selective_logistic | 0.661 |
| 2.0 | CARLA | selective_hist_gbm | 0.803 |
| 2.0 | KITTI | distance_gate | 0.700 |
| 2.0 | KITTI | OVI_geom | 0.710 |
| 2.0 | KITTI | selective_logistic | 0.844 |
| 2.0 | KITTI | selective_hist_gbm | 0.901 |
| 3.0 | CARLA | distance_gate | 0.661 |
| 3.0 | CARLA | OVI_geom | 0.660 |
| 3.0 | CARLA | selective_logistic | 0.663 |
| 3.0 | CARLA | selective_hist_gbm | 0.814 |
| 3.0 | KITTI | distance_gate | 0.702 |
| 3.0 | KITTI | OVI_geom | 0.719 |
| 3.0 | KITTI | selective_logistic | 0.851 |
| 3.0 | KITTI | selective_hist_gbm | 0.912 |
| 5.0 | CARLA | distance_gate | 0.656 |
| 5.0 | CARLA | OVI_geom | 0.655 |
| 5.0 | CARLA | selective_logistic | 0.675 |
| 5.0 | CARLA | selective_hist_gbm | 0.810 |
| 5.0 | KITTI | distance_gate | 0.707 |
| 5.0 | KITTI | OVI_geom | 0.730 |
| 5.0 | KITTI | selective_logistic | 0.861 |
| 5.0 | KITTI | selective_hist_gbm | 0.921 |

## 6. Refusal Pareto
- figure: figs/paper2_pareto.png (ok)
- lower curve = fewer overconfident-wrong velocities at equal retention = better.

## Honest reading
- Distance-gate is the Qiu-2018-style single-scalar observability gate baseline.
- A selective model is journal-meaningful only where it beats the gate with non-overlapping CIs AND generalizes cross-dataset; in-domain wins that vanish CARLA→KITTI indicate dataset-specific overfit.
- Report the most robust model (typically logistic) as headline; GBM/MLP as high-variance upper bound.
