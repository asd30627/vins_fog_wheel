# PAPER2_TCSV_RESULTS

> TCSV = Temporal-Consistency Selective Validator. CARLA n=15811, KITTI n=37022. Splits: CARLA by run, KITTI by sequence (NO frame random). Velocity criterion = ego-independent vel_err<=3 m/s. Features = 5 GEO + 2 TEMP-base + 7 TEMP-residual (all runtime-observable; only the LABEL uses GT). Window W=5 unless stated.

## 1. Operating evaluation by scenario (AUROC + selective-risk metrics)
| scenario | model | AUROC | overconf | retention | false_ref | F1_inv | AURC↓ | OC@ret.8 | OC@ret.9 |
|---|---|---|---|---|---|---|---|---|---|
| CARLA->CARLA(run) | no_policy | 0.500 | 0.856 | 1.000 | 0.000 | 0.000 | 0.831 | 0.856 | 0.856 |
| CARLA->CARLA(run) | distance_gate | 0.755 | 0.761 | 0.847 | 0.153 | 0.695 | 0.773 | 0.715 | 0.815 |
| CARLA->CARLA(run) | OVI_geom | 0.760 | 0.768 | 0.847 | 0.153 | 0.681 | 0.769 | 0.718 | 0.816 |
| CARLA->CARLA(run) | TCSV-rule | 0.726 | 0.790 | 0.968 | 0.032 | 0.555 | 0.810 | 0.790 | 0.790 |
| CARLA->CARLA(run) | TCSV-HistGBM | 0.800 | 0.695 | 0.570 | 0.430 | 0.843 | 0.703 | 0.747 | 0.754 |
| CARLA->CARLA(run) | TCSV-MLP | 0.738 | 0.753 | 0.652 | 0.348 | 0.772 | 0.734 | 0.783 | 0.808 |
| KITTI->KITTI(seq) | no_policy | 0.500 | 0.521 | 1.000 | 0.000 | 0.000 | 0.450 | 0.521 | 0.521 |
| KITTI->KITTI(seq) | distance_gate | 0.686 | 0.432 | 0.904 | 0.096 | 0.507 | 0.457 | 0.396 | 0.430 |
| KITTI->KITTI(seq) | OVI_geom | 0.732 | 0.392 | 0.859 | 0.141 | 0.606 | 0.385 | 0.367 | 0.411 |
| KITTI->KITTI(seq) | TCSV-rule | 0.820 | 0.353 | 0.863 | 0.137 | 0.670 | 0.277 | 0.353 | 0.464 |
| KITTI->KITTI(seq) | TCSV-HistGBM | 0.923 | 0.232 | 0.886 | 0.114 | 0.812 | 0.210 | 0.142 | 0.250 |
| KITTI->KITTI(seq) | TCSV-MLP | 0.922 | 0.196 | 0.866 | 0.134 | 0.836 | 0.211 | 0.143 | 0.239 |
| CARLA->KITTI | no_policy | 0.500 | 0.570 | 1.000 | 0.000 | 0.000 | 0.503 | 0.570 | 0.570 |
| CARLA->KITTI | distance_gate | 0.713 | 0.382 | 0.634 | 0.366 | 0.712 | 0.456 | 0.428 | 0.485 |
| CARLA->KITTI | OVI_geom | 0.711 | 0.390 | 0.632 | 0.368 | 0.705 | 0.456 | 0.432 | 0.486 |
| CARLA->KITTI | TCSV-rule | 0.640 | 0.553 | 0.557 | 0.443 | 0.530 | 0.448 | 0.482 | 0.482 |
| CARLA->KITTI | TCSV-HistGBM | 0.719 | 0.398 | 0.538 | 0.462 | 0.704 | 0.406 | 0.466 | 0.467 |
| CARLA->KITTI | TCSV-MLP | 0.689 | 0.421 | 0.638 | 0.362 | 0.676 | 0.416 | 0.491 | 0.525 |
| CARLA+KITtrain->KIThold | no_policy | 0.500 | 0.521 | 1.000 | 0.000 | 0.000 | 0.450 | 0.521 | 0.521 |
| CARLA+KITtrain->KIThold | distance_gate | 0.686 | 0.435 | 0.912 | 0.088 | 0.495 | 0.457 | 0.396 | 0.430 |
| CARLA+KITtrain->KIThold | OVI_geom | 0.728 | 0.402 | 0.880 | 0.120 | 0.584 | 0.390 | 0.366 | 0.411 |
| CARLA+KITtrain->KIThold | TCSV-rule | 0.775 | 0.390 | 0.913 | 0.087 | 0.602 | 0.326 | 0.331 | 0.390 |
| CARLA+KITtrain->KIThold | TCSV-HistGBM | 0.917 | 0.287 | 0.914 | 0.086 | 0.761 | 0.213 | 0.153 | 0.269 |
| CARLA+KITtrain->KIThold | TCSV-MLP | 0.881 | 0.257 | 0.845 | 0.155 | 0.781 | 0.236 | 0.222 | 0.319 |

## 2. Do the NEW temporal-residual features beat the prior OLD10 set? (HistGBM, in-domain)
| dataset | feats | AUROC | AURC↓ | overconf@ret.9 |
|---|---|---|---|---|
| CARLA | OLD10 | 0.829 | 0.686 | 0.739 |
| CARLA | TCSV14 | 0.800 | 0.703 | 0.754 |
| KITTI | OLD10 | 0.919 | 0.213 | 0.254 |
| KITTI | TCSV14 | 0.923 | 0.210 | 0.250 |

## 3. Permutation importance (HistGBM, ΔAUROC when feature shuffled; in-domain test)

**CARLA** — group totals: GEO=0.0442, TEMP_base=0.2474, TEMP_resid=0.0318
| rank | feature | group | importance | std |
|---|---|---|---|---|
| 1 | raw_speed | TEMP_base | 0.1929 | 0.0086 |
| 2 | track_age | TEMP_base | 0.0545 | 0.0062 |
| 3 | depth_m | GEO | 0.0322 | 0.0022 |
| 4 | bearing_deg | GEO | 0.0153 | 0.0024 |
| 5 | velocity_direction_flip_count | TEMP_resid | 0.0117 | 0.0023 |
| 6 | short_window_velocity_jitter | TEMP_resid | 0.0075 | 0.0018 |
| 7 | cv_residual | TEMP_resid | 0.0075 | 0.0020 |
| 8 | bbox_area | GEO | 0.0066 | 0.0023 |

**KITTI** — group totals: GEO=0.0604, TEMP_base=0.1570, TEMP_resid=0.0934
| rank | feature | group | importance | std |
|---|---|---|---|---|
| 1 | raw_speed | TEMP_base | 0.1397 | 0.0037 |
| 2 | cv_residual | TEMP_resid | 0.0606 | 0.0016 |
| 3 | range_m | GEO | 0.0279 | 0.0013 |
| 4 | bbox_area | GEO | 0.0189 | 0.0009 |
| 5 | track_age | TEMP_base | 0.0173 | 0.0007 |
| 6 | short_window_velocity_jitter | TEMP_resid | 0.0126 | 0.0004 |
| 7 | jerk_score | TEMP_resid | 0.0079 | 0.0008 |
| 8 | velocity_direction_flip_count | TEMP_resid | 0.0068 | 0.0006 |

## 4. Temporal-window ablation (in-domain HistGBM; W=1 collapses windowed features)
| W | dataset | AUROC | AURC↓ | overconf@ret.9 |
|---|---|---|---|---|
| 1 | CARLA | 0.813 | 0.699 | 0.710 |
| 1 | KITTI | 0.917 | 0.214 | 0.269 |
| 3 | CARLA | 0.807 | 0.701 | 0.742 |
| 3 | KITTI | 0.921 | 0.211 | 0.254 |
| 5 | CARLA | 0.800 | 0.703 | 0.754 |
| 5 | KITTI | 0.923 | 0.210 | 0.250 |
| 7 | CARLA | 0.824 | 0.695 | 0.740 |
| 7 | KITTI | 0.923 | 0.210 | 0.255 |

## 5. TCSV-rule (interpretable depth-3 tree, CARLA train) — the rule gate
```
|--- raw_speed <= 15.56
|   |--- velocity_direction_flip_count <= 0.50
|   |   |--- track_age <= 0.50
|   |   |   |--- class: 0
|   |   |--- track_age >  0.50
|   |   |   |--- class: 1
|   |--- velocity_direction_flip_count >  0.50
|   |   |--- raw_speed <= 0.11
|   |   |   |--- class: 0
|   |   |--- raw_speed >  0.11
|   |   |   |--- class: 1
|--- raw_speed >  15.56
|   |--- short_window_velocity_jitter <= 5.64
|   |   |--- class: 0
|   |--- short_window_velocity_jitter >  5.64
|   |   |--- range_m <= 98.52
|   |   |   |--- class: 0
|   |   |--- range_m >  98.52
|   |   |   |--- class: 0
```

## Honest verdict
- AURC (area under risk-coverage) is the cleanest selective-refusal summary (lower=better); overconf@ret.9 = the overconfident-wrong-velocity rate when forced to keep 90% of valid velocities.
- See §2 for whether the new temporal residuals actually add over the prior 10-feature model, and §3 for whether temporal-consistency features dominate importance. Both reported as-is, good or bad.
- Figure: figs/fig_tcsv_riskcov.png
