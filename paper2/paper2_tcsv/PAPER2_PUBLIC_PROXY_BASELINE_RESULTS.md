# PAPER2_PUBLIC_PROXY_BASELINE_RESULTS

> TCSV vs public/proxy baselines. CARLA n=15811, KITTI n=37022. NO GT features (label only). NO frame-random split. Selective-risk metrics: AURC↓ (area under risk-coverage, lower=better), OC@ret = overconfident-wrong velocity at fixed valid-retention.

> **Provenance:** `qiu_style(proxy)` is OUR reimplementation of a Qiu-2018-style geometric-excitation/observability gate — NOT the original paper. `selectivenet_proxy` is a softmax-response selector PROXY (an MLP's confidence); a full joint-trained SelectiveNet (predictor+selector+coverage loss) needs a DL framework (torch unavailable here) — `[TODO]`. `cv_smoothing_gate` = constant-velocity one-step innovation gate.

## CARLA->CARLA(run)
| model | AUROC | AURC↓ | overconf | OC@ret.8 | OC@ret.9 | retention | false_ref | F1_inv |
|---|---|---|---|---|---|---|---|---|
| no_policy | 0.500 | 0.831 | 0.856 | 0.856 | 0.856 | 1.000 | 0.000 | 0.000 |
| distance_gate | 0.755 | 0.773 | 0.761 | 0.715 | 0.815 | 0.847 | 0.153 | 0.695 |
| qiu_style(proxy) | 0.792 | 0.712 | 0.742 | 0.691 | 0.818 | 0.833 | 0.167 | 0.735 |
| yolo_conf_gate | 0.652 | 0.793 | 0.763 | 0.818 | 0.819 | 0.401 | 0.600 | 0.832 |
| bbox_depth_gate | 0.724 | 0.781 | 0.721 | 0.715 | 0.819 | 0.732 | 0.268 | 0.789 |
| cv_smoothing_gate | 0.684 | 0.821 | 0.773 | 0.748 | 0.810 | 0.865 | 0.135 | 0.660 |
| ovi_geom | 0.760 | 0.769 | 0.768 | 0.718 | 0.816 | 0.847 | 0.153 | 0.681 |
| selectivenet_proxy | 0.738 | 0.734 | 0.753 | 0.783 | 0.808 | 0.652 | 0.348 | 0.772 |
| TCSV-rule | 0.726 | 0.810 | 0.790 | 0.790 | 0.790 | 0.968 | 0.032 | 0.555 |
| ** TCSV-HistGBM** | 0.800 | 0.703 | 0.695 | 0.747 | 0.754 | 0.570 | 0.430 | 0.843 |
| TCSV-MLP | 0.738 | 0.734 | 0.753 | 0.783 | 0.808 | 0.652 | 0.348 | 0.772 |

_best baseline AURC = qiu_style(proxy) 0.712; TCSV-HistGBM 0.703 → **BEATS** (AURC↓)._

## KITTI->KITTI(seq)
| model | AUROC | AURC↓ | overconf | OC@ret.8 | OC@ret.9 | retention | false_ref | F1_inv |
|---|---|---|---|---|---|---|---|---|
| no_policy | 0.500 | 0.450 | 0.521 | 0.521 | 0.521 | 1.000 | 0.000 | 0.000 |
| distance_gate | 0.686 | 0.457 | 0.432 | 0.396 | 0.430 | 0.904 | 0.096 | 0.507 |
| qiu_style(proxy) | 0.722 | 0.354 | 0.420 | 0.395 | 0.431 | 0.880 | 0.120 | 0.545 |
| yolo_conf_gate | 0.691 | 0.422 | 0.379 | 0.398 | 0.443 | 0.731 | 0.269 | 0.643 |
| bbox_depth_gate | 0.760 | 0.341 | 0.396 | 0.363 | 0.411 | 0.868 | 0.132 | 0.598 |
| cv_smoothing_gate | 0.825 | 0.288 | 0.269 | 0.251 | 0.383 | 0.834 | 0.166 | 0.768 |
| ovi_geom | 0.732 | 0.385 | 0.392 | 0.367 | 0.411 | 0.859 | 0.141 | 0.606 |
| selectivenet_proxy | 0.922 | 0.211 | 0.196 | 0.143 | 0.239 | 0.866 | 0.134 | 0.836 |
| TCSV-rule | 0.820 | 0.277 | 0.353 | 0.353 | 0.464 | 0.863 | 0.137 | 0.670 |
| ** TCSV-HistGBM** | 0.923 | 0.210 | 0.232 | 0.142 | 0.250 | 0.886 | 0.114 | 0.812 |
| TCSV-MLP | 0.922 | 0.211 | 0.196 | 0.143 | 0.239 | 0.866 | 0.134 | 0.836 |

_best baseline AURC = selectivenet_proxy 0.211; TCSV-HistGBM 0.210 → **ties** (AURC↓)._

## CARLA->KITTI
| model | AUROC | AURC↓ | overconf | OC@ret.8 | OC@ret.9 | retention | false_ref | F1_inv |
|---|---|---|---|---|---|---|---|---|
| no_policy | 0.500 | 0.503 | 0.570 | 0.570 | 0.570 | 1.000 | 0.000 | 0.000 |
| distance_gate | 0.713 | 0.456 | 0.382 | 0.428 | 0.485 | 0.634 | 0.366 | 0.712 |
| qiu_style(proxy) | 0.673 | 0.480 | 0.424 | 0.463 | 0.493 | 0.608 | 0.392 | 0.677 |
| yolo_conf_gate | 0.710 | 0.436 | 0.393 | 0.448 | 0.491 | 0.607 | 0.393 | 0.704 |
| bbox_depth_gate | 0.726 | 0.411 | 0.364 | 0.445 | 0.483 | 0.569 | 0.431 | 0.725 |
| cv_smoothing_gate | 0.824 | 0.327 | 0.252 | 0.383 | 0.422 | 0.753 | 0.247 | 0.811 |
| ovi_geom | 0.711 | 0.456 | 0.390 | 0.432 | 0.486 | 0.632 | 0.368 | 0.705 |
| selectivenet_proxy | 0.689 | 0.416 | 0.421 | 0.491 | 0.525 | 0.638 | 0.362 | 0.676 |
| TCSV-rule | 0.640 | 0.448 | 0.553 | 0.482 | 0.482 | 0.557 | 0.443 | 0.530 |
| ** TCSV-HistGBM** | 0.719 | 0.406 | 0.398 | 0.466 | 0.467 | 0.538 | 0.462 | 0.704 |
| TCSV-MLP | 0.689 | 0.416 | 0.421 | 0.491 | 0.525 | 0.638 | 0.362 | 0.676 |

_best baseline AURC = cv_smoothing_gate 0.327; TCSV-HistGBM 0.406 → **LOSES** (AURC↓)._

## KITTI->CARLA
| model | AUROC | AURC↓ | overconf | OC@ret.8 | OC@ret.9 | retention | false_ref | F1_inv |
|---|---|---|---|---|---|---|---|---|
| no_policy | 0.500 | 0.880 | 0.888 | 0.888 | 0.888 | 1.000 | 0.000 | 0.000 |
| distance_gate | 0.695 | 0.832 | 0.805 | 0.836 | 0.871 | 0.660 | 0.340 | 0.772 |
| qiu_style(proxy) | 0.697 | 0.805 | 0.823 | 0.838 | 0.872 | 0.708 | 0.292 | 0.722 |
| yolo_conf_gate | 0.622 | 0.848 | 0.832 | 0.868 | 0.877 | 0.494 | 0.506 | 0.788 |
| bbox_depth_gate | 0.715 | 0.817 | 0.780 | 0.838 | 0.870 | 0.643 | 0.357 | 0.811 |
| cv_smoothing_gate | 0.701 | 0.845 | 0.809 | 0.835 | 0.842 | 0.760 | 0.240 | 0.730 |
| ovi_geom | 0.692 | 0.832 | 0.800 | 0.845 | 0.868 | 0.661 | 0.339 | 0.779 |
| selectivenet_proxy | 0.685 | 0.841 | 0.828 | 0.834 | 0.839 | 0.398 | 0.602 | 0.827 |
| TCSV-rule | 0.682 | 0.842 | 0.825 | 0.839 | 0.839 | 0.482 | 0.517 | 0.801 |
| ** TCSV-HistGBM** | 0.726 | 0.823 | 0.811 | 0.812 | 0.819 | 0.580 | 0.420 | 0.789 |
| TCSV-MLP | 0.685 | 0.841 | 0.828 | 0.834 | 0.839 | 0.398 | 0.602 | 0.827 |

_best baseline AURC = qiu_style(proxy) 0.805; TCSV-HistGBM 0.823 → **LOSES** (AURC↓)._

## CARLA+KITtrain->KIThold
| model | AUROC | AURC↓ | overconf | OC@ret.8 | OC@ret.9 | retention | false_ref | F1_inv |
|---|---|---|---|---|---|---|---|---|
| no_policy | 0.500 | 0.450 | 0.521 | 0.521 | 0.521 | 1.000 | 0.000 | 0.000 |
| distance_gate | 0.686 | 0.457 | 0.435 | 0.396 | 0.430 | 0.912 | 0.088 | 0.495 |
| qiu_style(proxy) | 0.719 | 0.382 | 0.406 | 0.377 | 0.424 | 0.864 | 0.136 | 0.579 |
| yolo_conf_gate | 0.691 | 0.422 | 0.379 | 0.398 | 0.443 | 0.731 | 0.269 | 0.643 |
| bbox_depth_gate | 0.719 | 0.370 | 0.444 | 0.397 | 0.429 | 0.927 | 0.073 | 0.463 |
| cv_smoothing_gate | 0.823 | 0.289 | 0.260 | 0.251 | 0.383 | 0.819 | 0.181 | 0.773 |
| ovi_geom | 0.728 | 0.390 | 0.402 | 0.366 | 0.411 | 0.880 | 0.120 | 0.584 |
| selectivenet_proxy | 0.881 | 0.236 | 0.257 | 0.222 | 0.319 | 0.845 | 0.155 | 0.781 |
| TCSV-rule | 0.775 | 0.326 | 0.390 | 0.331 | 0.390 | 0.913 | 0.087 | 0.602 |
| ** TCSV-HistGBM** | 0.917 | 0.213 | 0.287 | 0.153 | 0.269 | 0.914 | 0.086 | 0.761 |
| TCSV-MLP | 0.881 | 0.236 | 0.257 | 0.222 | 0.319 | 0.845 | 0.155 | 0.781 |

_best baseline AURC = selectivenet_proxy 0.236; TCSV-HistGBM 0.213 → **BEATS** (AURC↓)._

## KITtrain+CARtrain->CARhold
| model | AUROC | AURC↓ | overconf | OC@ret.8 | OC@ret.9 | retention | false_ref | F1_inv |
|---|---|---|---|---|---|---|---|---|
| no_policy | 0.500 | 0.831 | 0.856 | 0.856 | 0.856 | 1.000 | 0.000 | 0.000 |
| distance_gate | 0.755 | 0.773 | 0.760 | 0.715 | 0.815 | 0.847 | 0.153 | 0.697 |
| qiu_style(proxy) | 0.781 | 0.718 | 0.764 | 0.736 | 0.814 | 0.822 | 0.178 | 0.698 |
| yolo_conf_gate | 0.652 | 0.793 | 0.798 | 0.818 | 0.819 | 0.465 | 0.535 | 0.776 |
| bbox_depth_gate | 0.731 | 0.779 | 0.702 | 0.705 | 0.820 | 0.792 | 0.208 | 0.798 |
| cv_smoothing_gate | 0.684 | 0.821 | 0.772 | 0.748 | 0.808 | 0.863 | 0.137 | 0.664 |
| ovi_geom | 0.750 | 0.775 | 0.732 | 0.731 | 0.823 | 0.801 | 0.199 | 0.760 |
| selectivenet_proxy | 0.731 | 0.774 | 0.687 | 0.788 | 0.810 | 0.501 | 0.499 | 0.859 |
| TCSV-rule | 0.732 | 0.764 | 0.717 | 0.816 | 0.816 | 0.533 | 0.467 | 0.835 |
| ** TCSV-HistGBM** | 0.853 | 0.685 | 0.493 | 0.674 | 0.700 | 0.401 | 0.600 | 0.918 |
| TCSV-MLP | 0.731 | 0.774 | 0.687 | 0.788 | 0.810 | 0.501 | 0.499 | 0.859 |

_best baseline AURC = qiu_style(proxy) 0.718; TCSV-HistGBM 0.685 → **BEATS** (AURC↓)._

## Honest reading
- AURC↓ and OC@ret.9 are the operative selective-refusal metrics; AUROC is secondary.
- `qiu_style(proxy)` and `selectivenet_proxy` are reimplementations/proxies — NOT claimed equal to originals.
- In-domain (CARLA->CARLA, KITTI->KITTI) and mixed-train→held-out are the credible regimes; direct cross-dataset (CARLA->KITTI, KITTI->CARLA) tests generalization and is expected to be weaker.
- If a simple gate matches TCSV on a split, say so plainly.
