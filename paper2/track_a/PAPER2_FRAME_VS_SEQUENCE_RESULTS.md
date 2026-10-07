# PAPER2 Part 1 — FRAME vs SEQUENCE RESULTS

> Object-state validity (velocity_valid primary). CARLA n=23567 (4 towns), KITTI n=37022. Splits by group (CARLA town@run, KITTI kitti@seq) — NO frame-random, no track in both train/test. Sequence windows PAST-ONLY (edge-pad earliest), no future leak. Primary metric AURC (lower=better). torch=True. runtime=121.5s. Date 2026-07-01.

**Chosen deployable sequence config:** T=5, pool=full (best combined in-domain AURC rank).

**BEST_PER_FRAME_MODEL = `TCSV-HistGBM-bal`**  |  **BEST_SEQUENCE_MODEL = `seq_pool_hgbm`** (by mean in-domain AURC).

## 1. AURC↓ by split × model (primary)
| split        |   MLP(128,64) |   TCSV-HistGBM |   TCSV-HistGBM-bal |   TCSV-M(mono) |   bbox_gate |   conf_gate |   cv_smoothing_gate |   depth_gate |   distance_gate |   logistic |   logistic_balanced |   qiu_proxy(logit-geo) |   seq_GRU |   seq_TCN |   seq_Transformer |   seq_pool_hgbm |   seq_pool_mlp |
|:-------------|--------------:|---------------:|-------------------:|---------------:|------------:|------------:|--------------------:|-------------:|----------------:|-----------:|--------------------:|-----------------------:|----------:|----------:|------------------:|----------------:|---------------:|
| C+Ktr->Khold |        0.2324 |         0.2084 |             0.2086 |         0.2288 |      0.4403 |      0.4222 |              0.2842 |       0.4132 |          0.4572 |     0.2844 |              0.2912 |                 0.3947 |    0.2554 |    0.2953 |            0.2913 |          0.2035 |         0.217  |
| CARLA->CARLA |        0.8298 |         0.7978 |             0.7871 |         0.7725 |      0.8512 |      0.8268 |              0.8738 |       0.8569 |          0.8568 |     0.8357 |              0.8335 |                 0.8594 |    0.8081 |    0.8607 |            0.8456 |          0.7625 |         0.8167 |
| CARLA->KITTI |        0.3872 |         0.4093 |             0.4108 |         0.3958 |      0.4544 |      0.4366 |              0.3168 |       0.4325 |          0.4557 |     0.367  |              0.3597 |                 0.4641 |  nan      |  nan      |          nan      |          0.3887 |         0.4943 |
| K+Ctr->Chold |        0.8434 |         0.8033 |             0.8017 |         0.8216 |      0.8512 |      0.8268 |              0.8738 |       0.8569 |          0.8568 |     0.8161 |              0.816  |                 0.8553 |    0.8613 |    0.8678 |            0.8712 |          0.8045 |         0.8171 |
| KITTI->CARLA |        0.8405 |         0.829  |             0.8303 |         0.8341 |      0.8537 |      0.8467 |              0.8538 |       0.8345 |          0.8331 |     0.8031 |              0.803  |                 0.8328 |  nan      |  nan      |          nan      |          0.8313 |         0.849  |
| KITTI->KITTI |        0.2128 |         0.2053 |             0.2054 |         0.2232 |      0.4403 |      0.4222 |              0.2842 |       0.4132 |          0.4572 |     0.2486 |              0.2504 |                 0.3853 |    0.2453 |    0.2577 |            0.2842 |          0.1957 |         0.1884 |

## 2. Full operating metrics (velocity_valid)
| split | family | model | AUROC | AURC↓ | OC@ret.8↓ | OC@ret.9↓ | retention | F1_inv | fit_ms |
|---|---|---|---|---|---|---|---|---|---|
| C+Ktr->Khold | per_frame | TCSV-HistGBM | 0.928 | 0.208 | 0.137 | 0.226 | 0.856 | 0.848 | 405.100 |
| C+Ktr->Khold | per_frame | TCSV-HistGBM-bal | 0.928 | 0.209 | 0.136 | 0.227 | 0.831 | 0.851 | 511.800 |
| C+Ktr->Khold | per_frame | TCSV-M(mono) | 0.897 | 0.229 | 0.191 | 0.279 | 0.798 | 0.823 | 385.000 |
| C+Ktr->Khold | per_frame | MLP(128,64) | 0.888 | 0.232 | 0.209 | 0.304 | 0.788 | 0.815 | 4744.200 |
| C+Ktr->Khold | per_frame | cv_smoothing_gate | 0.836 | 0.284 | 0.251 | 0.320 | 0.814 | 0.776 | 0.000 |
| C+Ktr->Khold | per_frame | logistic | 0.823 | 0.284 | 0.293 | 0.346 | 0.812 | 0.738 | 267.500 |
| C+Ktr->Khold | per_frame | logistic_balanced | 0.817 | 0.291 | 0.296 | 0.351 | 0.807 | 0.736 | 447.200 |
| C+Ktr->Khold | per_frame | qiu_proxy(logit-geo) | 0.724 | 0.395 | 0.365 | 0.412 | 0.790 | 0.662 | 12.100 |
| C+Ktr->Khold | per_frame | depth_gate | 0.715 | 0.413 | 0.366 | 0.413 | 0.738 | 0.682 | 0.000 |
| C+Ktr->Khold | per_frame | conf_gate | 0.691 | 0.422 | 0.398 | 0.443 | 0.731 | 0.643 | 0.000 |
| C+Ktr->Khold | per_frame | bbox_gate | 0.697 | 0.440 | 0.380 | 0.425 | 0.737 | 0.670 | 0.000 |
| C+Ktr->Khold | per_frame | distance_gate | 0.686 | 0.457 | 0.396 | 0.430 | 0.732 | 0.655 | 0.000 |
| C+Ktr->Khold | sequence | seq_pool_hgbm | 0.936 | 0.203 | 0.117 | 0.201 | 0.854 | 0.863 | 433.400 |
| C+Ktr->Khold | sequence | seq_pool_mlp | 0.917 | 0.217 | 0.151 | 0.239 | 0.798 | 0.848 | 9553.900 |
| C+Ktr->Khold | sequence | seq_GRU | 0.865 | 0.255 | 0.231 | 0.304 | 0.811 | 0.792 | 1023.100 |
| C+Ktr->Khold | sequence | seq_Transformer | 0.800 | 0.291 | 0.328 | 0.395 | 0.711 | 0.739 | 3081.700 |
| C+Ktr->Khold | sequence | seq_TCN | 0.803 | 0.295 | 0.313 | 0.405 | 0.788 | 0.727 | 1226.900 |
| CARLA->CARLA | per_frame | TCSV-M(mono) | 0.872 | 0.772 | 0.730 | 0.777 | 0.843 | 0.845 | 230.800 |
| CARLA->CARLA | per_frame | TCSV-HistGBM-bal | 0.850 | 0.787 | 0.760 | 0.817 | 0.833 | 0.827 | 285.500 |
| CARLA->CARLA | per_frame | TCSV-HistGBM | 0.849 | 0.798 | 0.755 | 0.812 | 0.863 | 0.815 | 247.500 |
| CARLA->CARLA | per_frame | conf_gate | 0.732 | 0.827 | 0.873 | 0.898 | 0.645 | 0.866 | 0.000 |
| CARLA->CARLA | per_frame | MLP(128,64) | 0.779 | 0.830 | 0.814 | 0.834 | 0.854 | 0.734 | 2733.200 |
| CARLA->CARLA | per_frame | logistic_balanced | 0.767 | 0.834 | 0.831 | 0.846 | 0.938 | 0.625 | 20.100 |
| CARLA->CARLA | per_frame | logistic | 0.765 | 0.836 | 0.837 | 0.847 | 0.924 | 0.638 | 18.100 |
| CARLA->CARLA | per_frame | bbox_gate | 0.718 | 0.851 | 0.854 | 0.892 | 0.673 | 0.845 | 0.000 |
| CARLA->CARLA | per_frame | distance_gate | 0.711 | 0.857 | 0.854 | 0.883 | 0.698 | 0.766 | 0.000 |
| CARLA->CARLA | per_frame | depth_gate | 0.711 | 0.857 | 0.855 | 0.884 | 0.640 | 0.796 | 0.000 |
| CARLA->CARLA | per_frame | qiu_proxy(logit-geo) | 0.708 | 0.859 | 0.852 | 0.884 | 0.801 | 0.679 | 7.400 |
| CARLA->CARLA | per_frame | cv_smoothing_gate | 0.679 | 0.874 | 0.846 | 0.878 | 0.745 | 0.746 | 0.000 |
| CARLA->CARLA | sequence | seq_pool_hgbm | 0.880 | 0.762 | 0.721 | 0.794 | 0.788 | 0.880 | 289.600 |
| CARLA->CARLA | sequence | seq_GRU | 0.795 | 0.808 | 0.817 | 0.840 | 0.779 | 0.781 | 1705.000 |
| CARLA->CARLA | sequence | seq_pool_mlp | 0.797 | 0.817 | 0.815 | 0.846 | 0.732 | 0.822 | 2172.000 |
| CARLA->CARLA | sequence | seq_Transformer | 0.711 | 0.846 | 0.852 | 0.876 | 0.796 | 0.684 | 1217.900 |
| CARLA->CARLA | sequence | seq_TCN | 0.688 | 0.861 | 0.861 | 0.872 | 0.721 | 0.739 | 656.800 |
| CARLA->KITTI | per_frame | cv_smoothing_gate | 0.848 | 0.317 | 0.276 | 0.358 | 0.793 | 0.804 | 0.000 |
| CARLA->KITTI | per_frame | logistic_balanced | 0.789 | 0.360 | 0.384 | 0.430 | 0.754 | 0.727 | 49.900 |
| CARLA->KITTI | per_frame | logistic | 0.777 | 0.367 | 0.397 | 0.446 | 0.738 | 0.719 | 26.900 |
| CARLA->KITTI | per_frame | MLP(128,64) | 0.729 | 0.387 | 0.456 | 0.502 | 0.634 | 0.707 | 5083.100 |
| CARLA->KITTI | per_frame | TCSV-M(mono) | 0.715 | 0.396 | 0.464 | 0.476 | 0.920 | 0.514 | 269.800 |
| CARLA->KITTI | per_frame | TCSV-HistGBM | 0.709 | 0.409 | 0.469 | 0.475 | 0.942 | 0.509 | 474.400 |
| CARLA->KITTI | per_frame | TCSV-HistGBM-bal | 0.706 | 0.411 | 0.471 | 0.474 | 0.927 | 0.516 | 328.500 |
| CARLA->KITTI | per_frame | depth_gate | 0.730 | 0.432 | 0.422 | 0.480 | 0.712 | 0.707 | 0.000 |
| CARLA->KITTI | per_frame | conf_gate | 0.710 | 0.437 | 0.448 | 0.491 | 0.725 | 0.667 | 0.000 |
| CARLA->KITTI | per_frame | bbox_gate | 0.716 | 0.454 | 0.427 | 0.481 | 0.729 | 0.690 | 0.000 |
| CARLA->KITTI | per_frame | distance_gate | 0.713 | 0.456 | 0.428 | 0.485 | 0.728 | 0.683 | 0.000 |
| CARLA->KITTI | per_frame | qiu_proxy(logit-geo) | 0.702 | 0.464 | 0.440 | 0.489 | 0.737 | 0.666 | 13.100 |
| CARLA->KITTI | sequence | seq_pool_hgbm | 0.732 | 0.389 | 0.453 | 0.467 | 0.891 | 0.554 | 363.400 |
| CARLA->KITTI | sequence | seq_pool_mlp | 0.628 | 0.494 | 0.522 | 0.535 | 0.584 | 0.626 | 3805.200 |
| K+Ctr->Chold | per_frame | TCSV-HistGBM-bal | 0.820 | 0.802 | 0.799 | 0.828 | 0.791 | 0.808 | 422.300 |
| K+Ctr->Chold | per_frame | TCSV-HistGBM | 0.815 | 0.803 | 0.798 | 0.826 | 0.801 | 0.794 | 483.000 |
| K+Ctr->Chold | per_frame | logistic_balanced | 0.784 | 0.816 | 0.837 | 0.848 | 0.710 | 0.799 | 294.300 |
| K+Ctr->Chold | per_frame | logistic | 0.781 | 0.816 | 0.839 | 0.847 | 0.755 | 0.768 | 262.200 |
| K+Ctr->Chold | per_frame | TCSV-M(mono) | 0.799 | 0.822 | 0.801 | 0.826 | 0.852 | 0.765 | 320.900 |
| K+Ctr->Chold | per_frame | conf_gate | 0.732 | 0.827 | 0.873 | 0.898 | 0.645 | 0.866 | 0.000 |
| K+Ctr->Chold | per_frame | MLP(128,64) | 0.764 | 0.843 | 0.826 | 0.837 | 0.877 | 0.712 | 5836.200 |
| K+Ctr->Chold | per_frame | bbox_gate | 0.718 | 0.851 | 0.854 | 0.892 | 0.673 | 0.845 | 0.000 |
| K+Ctr->Chold | per_frame | qiu_proxy(logit-geo) | 0.712 | 0.855 | 0.853 | 0.883 | 0.584 | 0.833 | 14.100 |
| K+Ctr->Chold | per_frame | distance_gate | 0.711 | 0.857 | 0.854 | 0.883 | 0.698 | 0.766 | 0.000 |
| K+Ctr->Chold | per_frame | depth_gate | 0.711 | 0.857 | 0.855 | 0.884 | 0.640 | 0.796 | 0.000 |
| K+Ctr->Chold | per_frame | cv_smoothing_gate | 0.679 | 0.874 | 0.846 | 0.878 | 0.745 | 0.746 | 0.000 |
| K+Ctr->Chold | sequence | seq_pool_hgbm | 0.827 | 0.804 | 0.785 | 0.811 | 0.865 | 0.779 | 509.000 |
| K+Ctr->Chold | sequence | seq_pool_mlp | 0.789 | 0.817 | 0.826 | 0.840 | 0.927 | 0.662 | 8502.600 |
| K+Ctr->Chold | sequence | seq_GRU | 0.720 | 0.861 | 0.848 | 0.852 | 0.958 | 0.592 | 650.700 |
| K+Ctr->Chold | sequence | seq_TCN | 0.676 | 0.868 | 0.860 | 0.871 | 0.801 | 0.650 | 880.800 |
| K+Ctr->Chold | sequence | seq_Transformer | 0.683 | 0.871 | 0.865 | 0.878 | 0.717 | 0.731 | 2204.600 |
| KITTI->CARLA | per_frame | logistic_balanced | 0.767 | 0.803 | 0.809 | 0.828 | 0.787 | 0.747 | 140.300 |
| KITTI->CARLA | per_frame | logistic | 0.766 | 0.803 | 0.809 | 0.828 | 0.782 | 0.752 | 134.900 |
| KITTI->CARLA | per_frame | TCSV-HistGBM | 0.742 | 0.829 | 0.809 | 0.818 | 0.929 | 0.658 | 531.900 |
| KITTI->CARLA | per_frame | TCSV-HistGBM-bal | 0.740 | 0.830 | 0.810 | 0.819 | 0.926 | 0.657 | 498.100 |
| KITTI->CARLA | per_frame | qiu_proxy(logit-geo) | 0.715 | 0.833 | 0.835 | 0.867 | 0.673 | 0.787 | 9.700 |
| KITTI->CARLA | per_frame | distance_gate | 0.721 | 0.833 | 0.826 | 0.867 | 0.701 | 0.780 | 0.000 |
| KITTI->CARLA | per_frame | TCSV-M(mono) | 0.739 | 0.834 | 0.810 | 0.819 | 0.933 | 0.650 | 315.300 |
| KITTI->CARLA | per_frame | depth_gate | 0.719 | 0.835 | 0.832 | 0.871 | 0.656 | 0.804 | 0.000 |
| KITTI->CARLA | per_frame | MLP(128,64) | 0.726 | 0.841 | 0.818 | 0.826 | 0.907 | 0.648 | 3524.500 |
| KITTI->CARLA | per_frame | conf_gate | 0.645 | 0.847 | 0.869 | 0.884 | 0.504 | 0.819 | 0.000 |
| KITTI->CARLA | per_frame | bbox_gate | 0.672 | 0.854 | 0.849 | 0.866 | 0.819 | 0.608 | 0.000 |
| KITTI->CARLA | per_frame | cv_smoothing_gate | 0.681 | 0.854 | 0.825 | 0.893 | 0.753 | 0.750 | 0.000 |
| KITTI->CARLA | sequence | seq_pool_hgbm | 0.749 | 0.831 | 0.800 | 0.812 | 0.873 | 0.715 | 387.400 |
| KITTI->CARLA | sequence | seq_pool_mlp | 0.691 | 0.849 | 0.835 | 0.833 | 0.967 | 0.581 | 8454.700 |
| KITTI->KITTI | per_frame | TCSV-HistGBM | 0.934 | 0.205 | 0.122 | 0.217 | 0.830 | 0.861 | 283.600 |
| KITTI->KITTI | per_frame | TCSV-HistGBM-bal | 0.934 | 0.205 | 0.122 | 0.216 | 0.846 | 0.856 | 392.700 |
| KITTI->KITTI | per_frame | MLP(128,64) | 0.921 | 0.213 | 0.141 | 0.234 | 0.827 | 0.850 | 2550.000 |
| KITTI->KITTI | per_frame | TCSV-M(mono) | 0.905 | 0.223 | 0.174 | 0.279 | 0.797 | 0.835 | 322.200 |
| KITTI->KITTI | per_frame | logistic | 0.860 | 0.249 | 0.259 | 0.329 | 0.817 | 0.768 | 17.900 |
| KITTI->KITTI | per_frame | logistic_balanced | 0.858 | 0.250 | 0.262 | 0.329 | 0.790 | 0.773 | 18.600 |
| KITTI->KITTI | per_frame | cv_smoothing_gate | 0.836 | 0.284 | 0.251 | 0.320 | 0.814 | 0.776 | 0.000 |
| KITTI->KITTI | per_frame | qiu_proxy(logit-geo) | 0.732 | 0.385 | 0.367 | 0.411 | 0.754 | 0.672 | 7.800 |
| KITTI->KITTI | per_frame | depth_gate | 0.715 | 0.413 | 0.366 | 0.413 | 0.738 | 0.682 | 0.000 |
| KITTI->KITTI | per_frame | conf_gate | 0.691 | 0.422 | 0.398 | 0.443 | 0.731 | 0.643 | 0.000 |
| KITTI->KITTI | per_frame | bbox_gate | 0.697 | 0.440 | 0.380 | 0.425 | 0.737 | 0.670 | 0.000 |
| KITTI->KITTI | per_frame | distance_gate | 0.686 | 0.457 | 0.396 | 0.430 | 0.732 | 0.655 | 0.000 |
| KITTI->KITTI | sequence | seq_pool_mlp | 0.965 | 0.188 | 0.058 | 0.109 | 0.914 | 0.903 | 3647.300 |
| KITTI->KITTI | sequence | seq_pool_hgbm | 0.951 | 0.196 | 0.088 | 0.171 | 0.841 | 0.882 | 344.900 |
| KITTI->KITTI | sequence | seq_GRU | 0.870 | 0.245 | 0.225 | 0.317 | 0.809 | 0.798 | 703.800 |
| KITTI->KITTI | sequence | seq_TCN | 0.862 | 0.258 | 0.248 | 0.321 | 0.776 | 0.791 | 904.900 |
| KITTI->KITTI | sequence | seq_Transformer | 0.806 | 0.284 | 0.330 | 0.392 | 0.698 | 0.741 | 1436.200 |

## 3. Sequence T × pooling sweep (in-domain AURC↓, pool_hgbm)

**carla**
|   T |   full |   last |    max |   mean |   mean_std_last |   quantile |    std |
|----:|-------:|-------:|-------:|-------:|----------------:|-----------:|-------:|
|   3 | 0.771  |  0.802 | 0.8252 | 0.8149 |          0.7811 |     0.811  | 0.8141 |
|   5 | 0.7625 |  0.802 | 0.8374 | 0.829  |          0.7742 |     0.8219 | 0.817  |
|   7 | 0.7657 |  0.802 | 0.8381 | 0.8198 |          0.7731 |     0.8208 | 0.8181 |
|  10 | 0.7675 |  0.802 | 0.8436 | 0.8152 |          0.7759 |     0.8134 | 0.8211 |
|  15 | 0.7654 |  0.802 | 0.8469 | 0.8277 |          0.7734 |     0.8173 | 0.8158 |

**kitti**
|   T |   full |   last |    max |   mean |   mean_std_last |   quantile |    std |
|----:|-------:|-------:|-------:|-------:|----------------:|-----------:|-------:|
|   3 | 0.1932 | 0.2113 | 0.235  | 0.2355 |          0.1957 |     0.2307 | 0.2287 |
|   5 | 0.1957 | 0.2113 | 0.2469 | 0.2467 |          0.1965 |     0.25   | 0.2465 |
|   7 | 0.1978 | 0.2113 | 0.2564 | 0.2545 |          0.1981 |     0.2536 | 0.2575 |
|  10 | 0.199  | 0.2113 | 0.2672 | 0.2645 |          0.199  |     0.2632 | 0.2685 |
|  15 | 0.2003 | 0.2113 | 0.2814 | 0.2798 |          0.2003 |     0.277  | 0.2831 |

## 4. Paired bootstrap ΔAURC over groups (cand − ref); neg & CI<0 ⇒ cand better
| split | comparison | ΔAURC | CI low | CI high | verdict |
|---|---|---|---|---|---|
| CARLA->CARLA | seq_pool_hgbm vs TCSV-HistGBM-bal | -0.022 | -0.051 | 0.002 | tie |
| CARLA->CARLA | seq_pool_hgbm vs cv_gate | -0.111 | -0.140 | -0.080 | cand_better |
| CARLA->CARLA | TCSV-HistGBM-bal vs cv_gate | -0.088 | -0.126 | -0.060 | cand_better |
| KITTI->KITTI | seq_pool_hgbm vs TCSV-HistGBM-bal | -0.011 | -0.018 | -0.008 | cand_better |
| KITTI->KITTI | seq_pool_hgbm vs cv_gate | -0.090 | -0.121 | -0.073 | cand_better |
| KITTI->KITTI | TCSV-HistGBM-bal vs cv_gate | -0.079 | -0.107 | -0.066 | cand_better |
| C+Ktr->Khold | seq_pool_hgbm vs TCSV-HistGBM-bal | -0.006 | -0.009 | -0.003 | cand_better |
| C+Ktr->Khold | seq_pool_hgbm vs cv_gate | -0.083 | -0.117 | -0.064 | cand_better |
| C+Ktr->Khold | TCSV-HistGBM-bal vs cv_gate | -0.077 | -0.108 | -0.060 | cand_better |
| K+Ctr->Chold | seq_pool_hgbm vs TCSV-HistGBM-bal | 0.005 | -0.006 | 0.031 | tie |
| K+Ctr->Chold | seq_pool_hgbm vs cv_gate | -0.067 | -0.102 | -0.033 | cand_better |
| K+Ctr->Chold | TCSV-HistGBM-bal vs cv_gate | -0.072 | -0.110 | -0.036 | cand_better |

## 5. Multi-label feasibility (position_valid, full_state_valid; in-domain)
| label | dataset | model | n | base | AUROC | AURC↓ | OC@ret.9↓ |
|---|---|---|---|---|---|---|---|
| position_valid | carla | perframe_TCSV-HistGBM | 6857 | 0.367 | 0.742 | 0.516 | 0.516 |
| position_valid | carla | seq_pool_hgbm(T5,full) | 6857 | 0.367 | 0.753 | 0.495 | 0.504 |
| position_valid | kitti | perframe_TCSV-HistGBM | 13452 | 0.798 | 0.963 | 0.031 | 0.030 |
| position_valid | kitti | seq_pool_hgbm(T5,full) | 13452 | 0.798 | 0.939 | 0.038 | 0.040 |
| full_state_valid | carla | perframe_TCSV-HistGBM | 6857 | 0.045 | 0.853 | 0.894 | 0.904 |
| full_state_valid | carla | seq_pool_hgbm(T5,full) | 6857 | 0.045 | 0.862 | 0.885 | 0.896 |
| full_state_valid | kitti | perframe_TCSV-HistGBM | 13452 | 0.423 | 0.924 | 0.261 | 0.265 |
| full_state_valid | kitti | seq_pool_hgbm(T5,full) | 13452 | 0.423 | 0.931 | 0.259 | 0.227 |

## 6. Per-frame model ranking (mean in-domain AURC↓)
- TCSV-HistGBM-bal: 0.4962
- TCSV-M(mono): 0.4978
- TCSV-HistGBM: 0.5015
- MLP(128,64): 0.5213
- logistic_balanced: 0.5420
- logistic: 0.5422
- cv_smoothing_gate: 0.5790
- qiu_proxy(logit-geo): 0.6224
- conf_gate: 0.6245
- depth_gate: 0.6350
- bbox_gate: 0.6458
- distance_gate: 0.6570

## 7. Sequence model ranking (mean in-domain AURC↓)
- seq_pool_hgbm: 0.4791
- seq_pool_mlp: 0.5026
- seq_GRU: 0.5267
- seq_TCN: 0.5592
- seq_Transformer: 0.5649
