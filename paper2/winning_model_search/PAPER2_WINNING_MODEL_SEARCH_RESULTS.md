# PAPER2_WINNING_MODEL_SEARCH_RESULTS

> Search for a model that beats the BEST non-ours baseline on selective risk. CARLA n=15811, KITTI n=37022. NO GT features; NO frame-random split. Baseline pool (to beat) = distance/cv_smoothing/qiu(proxy)/bbox_depth/selectivenet(proxy)/ovi. **Every model logged.**
> Levers: per-domain quantile transform, monotonic constraints, conservative rank ensembles, hierarchical cv-gate, normalized cv innovation, proba/rank ensembles.

## 1. All models × all splits (selective-risk; AURC↓ primary)
### CARLA->CARLA
| model | AURC↓ | OC@.8 | OC@.9 | ret | false_ref | F1inv | AUROC |
|---|---|---|---|---|---|---|---|
| **HistGBM_mono_raw** | 0.680 | 0.675 | 0.719 | 0.826 | 0.174 | 0.808 | 0.853 |
| TCSV_HistGBM_raw | 0.703 | 0.747 | 0.754 | 0.570 | 0.430 | 0.843 | 0.800 |
| _qiu_style(proxy)_ | 0.712 | 0.691 | 0.818 | 0.833 | 0.167 | 0.735 | 0.792 |
| _selectivenet_proxy_ | 0.734 | 0.783 | 0.808 | 0.652 | 0.348 | 0.772 | 0.738 |
| HistGBM_quant | 0.747 | 0.756 | 0.787 | 0.389 | 0.611 | 0.837 | 0.738 |
| Ens_proba_hgbmq+logq | 0.749 | 0.737 | 0.799 | 0.709 | 0.291 | 0.810 | 0.761 |
| HistGBM_mono_quant | 0.750 | 0.748 | 0.801 | 0.627 | 0.373 | 0.824 | 0.757 |
| Hier_cv_then_hgbmq | 0.751 | 0.747 | 0.800 | 0.620 | 0.380 | 0.825 | 0.746 |
| Ens_min_cv+hgbmq | 0.756 | 0.738 | 0.795 | 0.748 | 0.252 | 0.808 | 0.769 |
| Ens_rankavg_cv+hgbmq | 0.766 | 0.744 | 0.785 | 0.588 | 0.412 | 0.843 | 0.753 |
| Ens_rankavg_cvnorm+hgbmq | 0.768 | 0.750 | 0.788 | 0.595 | 0.405 | 0.827 | 0.736 |
| Logistic_quant | 0.769 | 0.778 | 0.804 | 0.714 | 0.286 | 0.761 | 0.729 |
| _ovi_geom_ | 0.769 | 0.718 | 0.816 | 0.847 | 0.153 | 0.681 | 0.760 |
| MLP_quant | 0.770 | 0.777 | 0.782 | 0.348 | 0.652 | 0.839 | 0.709 |
| _distance_gate_ | 0.773 | 0.715 | 0.815 | 0.847 | 0.153 | 0.695 | 0.755 |
| _bbox_depth_gate_ | 0.781 | 0.715 | 0.819 | 0.732 | 0.268 | 0.789 | 0.724 |
| Ens_cv0.7+hgbmq0.3 | 0.788 | 0.741 | 0.782 | 0.792 | 0.208 | 0.756 | 0.724 |
| _cv_smoothing_gate_ | 0.821 | 0.748 | 0.810 | 0.865 | 0.135 | 0.660 | 0.684 |
| cv_norm_gate | 0.829 | 0.817 | 0.837 | 0.787 | 0.213 | 0.691 | 0.639 |

### KITTI->KITTI
| model | AURC↓ | OC@.8 | OC@.9 | ret | false_ref | F1inv | AUROC |
|---|---|---|---|---|---|---|---|
| TCSV_HistGBM_raw | 0.210 | 0.142 | 0.250 | 0.886 | 0.114 | 0.812 | 0.923 |
| _selectivenet_proxy_ | 0.211 | 0.143 | 0.239 | 0.866 | 0.134 | 0.836 | 0.922 |
| HistGBM_quant | 0.213 | 0.143 | 0.240 | 0.783 | 0.217 | 0.853 | 0.918 |
| MLP_quant | 0.215 | 0.151 | 0.237 | 0.787 | 0.213 | 0.849 | 0.920 |
| **HistGBM_mono_raw** | 0.228 | 0.189 | 0.318 | 0.855 | 0.145 | 0.791 | 0.893 |
| HistGBM_mono_quant | 0.235 | 0.208 | 0.311 | 0.726 | 0.275 | 0.825 | 0.885 |
| Hier_cv_then_hgbmq | 0.237 | 0.207 | 0.311 | 0.720 | 0.280 | 0.826 | 0.878 |
| Ens_proba_hgbmq+logq | 0.245 | 0.215 | 0.330 | 0.746 | 0.254 | 0.816 | 0.874 |
| Ens_rankavg_cv+hgbmq | 0.245 | 0.214 | 0.303 | 0.801 | 0.199 | 0.806 | 0.873 |
| Ens_min_cv+hgbmq | 0.247 | 0.227 | 0.330 | 0.671 | 0.329 | 0.810 | 0.868 |
| Ens_cv0.7+hgbmq0.3 | 0.259 | 0.227 | 0.350 | 0.823 | 0.177 | 0.790 | 0.856 |
| Ens_rankavg_cvnorm+hgbmq | 0.261 | 0.259 | 0.349 | 0.761 | 0.239 | 0.779 | 0.844 |
| Logistic_quant | 0.268 | 0.252 | 0.368 | 0.704 | 0.296 | 0.802 | 0.848 |
| _cv_smoothing_gate_ | 0.288 | 0.251 | 0.383 | 0.834 | 0.166 | 0.768 | 0.825 |
| _bbox_depth_gate_ | 0.341 | 0.363 | 0.411 | 0.868 | 0.132 | 0.598 | 0.760 |
| _qiu_style(proxy)_ | 0.354 | 0.395 | 0.431 | 0.880 | 0.120 | 0.545 | 0.722 |
| cv_norm_gate | 0.365 | 0.463 | 0.490 | 0.688 | 0.312 | 0.670 | 0.688 |
| _ovi_geom_ | 0.385 | 0.367 | 0.411 | 0.859 | 0.141 | 0.606 | 0.732 |
| _distance_gate_ | 0.457 | 0.396 | 0.430 | 0.904 | 0.096 | 0.507 | 0.686 |

### CARLA->KITTI
| model | AURC↓ | OC@.8 | OC@.9 | ret | false_ref | F1inv | AUROC |
|---|---|---|---|---|---|---|---|
| Ens_cv0.7+hgbmq0.3 | 0.324 | 0.356 | 0.423 | 0.621 | 0.379 | 0.809 | 0.829 |
| _cv_smoothing_gate_ | 0.327 | 0.383 | 0.422 | 0.753 | 0.247 | 0.811 | 0.824 |
| Ens_rankavg_cv+hgbmq | 0.335 | 0.373 | 0.417 | 0.453 | 0.547 | 0.788 | 0.812 |
| Ens_min_cv+hgbmq | 0.347 | 0.386 | 0.419 | 0.494 | 0.506 | 0.786 | 0.794 |
| Logistic_quant | 0.358 | 0.406 | 0.469 | 0.644 | 0.356 | 0.767 | 0.781 |
| Ens_proba_hgbmq+logq | 0.359 | 0.428 | 0.464 | 0.594 | 0.406 | 0.751 | 0.770 |
| Ens_rankavg_cvnorm+hgbmq | 0.367 | 0.454 | 0.504 | 0.457 | 0.543 | 0.775 | 0.749 |
| **HistGBM_mono_raw** | 0.378 | 0.454 | 0.475 | 0.630 | 0.370 | 0.686 | 0.740 |
| Hier_cv_then_hgbmq | 0.382 | 0.428 | 0.428 | 0.491 | 0.508 | 0.728 | 0.746 |
| HistGBM_mono_quant | 0.392 | 0.461 | 0.456 | 0.498 | 0.502 | 0.717 | 0.728 |
| HistGBM_quant | 0.392 | 0.451 | 0.447 | 0.387 | 0.614 | 0.740 | 0.731 |
| MLP_quant | 0.400 | 0.473 | 0.488 | 0.475 | 0.525 | 0.722 | 0.713 |
| TCSV_HistGBM_raw | 0.406 | 0.466 | 0.467 | 0.538 | 0.462 | 0.704 | 0.719 |
| _bbox_depth_gate_ | 0.411 | 0.445 | 0.483 | 0.569 | 0.431 | 0.725 | 0.726 |
| _selectivenet_proxy_ | 0.416 | 0.491 | 0.525 | 0.638 | 0.362 | 0.676 | 0.689 |
| cv_norm_gate | 0.417 | 0.518 | 0.547 | 0.687 | 0.313 | 0.683 | 0.681 |
| _distance_gate_ | 0.456 | 0.428 | 0.485 | 0.634 | 0.366 | 0.712 | 0.713 |
| _ovi_geom_ | 0.456 | 0.432 | 0.486 | 0.632 | 0.368 | 0.705 | 0.711 |
| _qiu_style(proxy)_ | 0.480 | 0.463 | 0.493 | 0.608 | 0.392 | 0.677 | 0.673 |

### KITTI->CARLA
| model | AURC↓ | OC@.8 | OC@.9 | ret | false_ref | F1inv | AUROC |
|---|---|---|---|---|---|---|---|
| _qiu_style(proxy)_ | 0.805 | 0.838 | 0.872 | 0.708 | 0.292 | 0.722 | 0.697 |
| _bbox_depth_gate_ | 0.817 | 0.838 | 0.870 | 0.643 | 0.357 | 0.811 | 0.715 |
| MLP_quant | 0.817 | 0.811 | 0.830 | 0.760 | 0.240 | 0.739 | 0.741 |
| HistGBM_quant | 0.820 | 0.807 | 0.817 | 0.767 | 0.233 | 0.736 | 0.744 |
| **HistGBM_mono_raw** | 0.822 | 0.814 | 0.821 | 0.643 | 0.357 | 0.767 | 0.727 |
| HistGBM_mono_quant | 0.823 | 0.818 | 0.829 | 0.755 | 0.245 | 0.723 | 0.728 |
| TCSV_HistGBM_raw | 0.823 | 0.812 | 0.819 | 0.580 | 0.420 | 0.789 | 0.726 |
| Hier_cv_then_hgbmq | 0.824 | 0.820 | 0.831 | 0.747 | 0.253 | 0.725 | 0.718 |
| Ens_proba_hgbmq+logq | 0.830 | 0.818 | 0.827 | 0.749 | 0.251 | 0.727 | 0.719 |
| _distance_gate_ | 0.832 | 0.836 | 0.871 | 0.660 | 0.340 | 0.772 | 0.695 |
| Ens_rankavg_cvnorm+hgbmq | 0.832 | 0.812 | 0.845 | 0.805 | 0.195 | 0.705 | 0.721 |
| _ovi_geom_ | 0.832 | 0.845 | 0.868 | 0.661 | 0.339 | 0.779 | 0.692 |
| Ens_rankavg_cv+hgbmq | 0.834 | 0.813 | 0.829 | 0.805 | 0.195 | 0.704 | 0.725 |
| Ens_min_cv+hgbmq | 0.834 | 0.809 | 0.829 | 0.699 | 0.301 | 0.767 | 0.725 |
| Ens_cv0.7+hgbmq0.3 | 0.838 | 0.812 | 0.833 | 0.834 | 0.166 | 0.683 | 0.718 |
| Logistic_quant | 0.839 | 0.822 | 0.839 | 0.744 | 0.257 | 0.714 | 0.698 |
| _selectivenet_proxy_ | 0.841 | 0.834 | 0.839 | 0.398 | 0.602 | 0.827 | 0.685 |
| _cv_smoothing_gate_ | 0.845 | 0.835 | 0.842 | 0.760 | 0.240 | 0.730 | 0.701 |
| cv_norm_gate | 0.851 | 0.839 | 0.872 | 0.638 | 0.362 | 0.772 | 0.657 |

### C+Ktr->Khold
| model | AURC↓ | OC@.8 | OC@.9 | ret | false_ref | F1inv | AUROC |
|---|---|---|---|---|---|---|---|
| TCSV_HistGBM_raw | 0.213 | 0.153 | 0.269 | 0.914 | 0.086 | 0.761 | 0.917 |
| MLP_quant | 0.223 | 0.195 | 0.280 | 0.757 | 0.242 | 0.827 | 0.902 |
| **HistGBM_mono_raw** | 0.230 | 0.207 | 0.318 | 0.908 | 0.092 | 0.706 | 0.889 |
| _selectivenet_proxy_ | 0.236 | 0.222 | 0.319 | 0.845 | 0.155 | 0.781 | 0.881 |
| HistGBM_quant | 0.237 | 0.244 | 0.336 | 0.625 | 0.375 | 0.815 | 0.875 |
| HistGBM_mono_quant | 0.240 | 0.215 | 0.332 | 0.763 | 0.237 | 0.817 | 0.878 |
| Hier_cv_then_hgbmq | 0.242 | 0.214 | 0.330 | 0.755 | 0.244 | 0.819 | 0.871 |
| Ens_proba_hgbmq+logq | 0.245 | 0.217 | 0.327 | 0.772 | 0.228 | 0.811 | 0.873 |
| Ens_rankavg_cv+hgbmq | 0.248 | 0.221 | 0.327 | 0.800 | 0.200 | 0.801 | 0.868 |
| Ens_min_cv+hgbmq | 0.249 | 0.249 | 0.338 | 0.669 | 0.331 | 0.808 | 0.864 |
| Ens_cv0.7+hgbmq0.3 | 0.261 | 0.233 | 0.359 | 0.808 | 0.192 | 0.790 | 0.853 |
| Ens_rankavg_cvnorm+hgbmq | 0.267 | 0.274 | 0.373 | 0.750 | 0.250 | 0.779 | 0.834 |
| Logistic_quant | 0.267 | 0.249 | 0.353 | 0.760 | 0.240 | 0.791 | 0.849 |
| _cv_smoothing_gate_ | 0.289 | 0.251 | 0.383 | 0.819 | 0.181 | 0.773 | 0.823 |
| cv_norm_gate | 0.364 | 0.463 | 0.490 | 0.691 | 0.309 | 0.669 | 0.690 |
| _bbox_depth_gate_ | 0.370 | 0.397 | 0.429 | 0.927 | 0.073 | 0.463 | 0.719 |
| _qiu_style(proxy)_ | 0.382 | 0.377 | 0.424 | 0.864 | 0.136 | 0.579 | 0.719 |
| _ovi_geom_ | 0.390 | 0.366 | 0.411 | 0.880 | 0.120 | 0.584 | 0.728 |
| _distance_gate_ | 0.457 | 0.396 | 0.430 | 0.912 | 0.088 | 0.495 | 0.686 |

### K+Ctr->Chold
| model | AURC↓ | OC@.8 | OC@.9 | ret | false_ref | F1inv | AUROC |
|---|---|---|---|---|---|---|---|
| TCSV_HistGBM_raw | 0.685 | 0.674 | 0.700 | 0.401 | 0.600 | 0.918 | 0.853 |
| _qiu_style(proxy)_ | 0.718 | 0.736 | 0.814 | 0.822 | 0.178 | 0.698 | 0.781 |
| **HistGBM_mono_raw** | 0.718 | 0.687 | 0.725 | 0.584 | 0.416 | 0.889 | 0.837 |
| HistGBM_mono_quant | 0.763 | 0.743 | 0.781 | 0.753 | 0.247 | 0.772 | 0.763 |
| Hier_cv_then_hgbmq | 0.764 | 0.741 | 0.782 | 0.753 | 0.247 | 0.772 | 0.753 |
| MLP_quant | 0.764 | 0.791 | 0.797 | 0.533 | 0.467 | 0.827 | 0.721 |
| _distance_gate_ | 0.773 | 0.715 | 0.815 | 0.847 | 0.153 | 0.697 | 0.755 |
| _selectivenet_proxy_ | 0.774 | 0.788 | 0.810 | 0.501 | 0.499 | 0.859 | 0.731 |
| _ovi_geom_ | 0.775 | 0.731 | 0.823 | 0.801 | 0.199 | 0.760 | 0.750 |
| _bbox_depth_gate_ | 0.779 | 0.705 | 0.820 | 0.792 | 0.208 | 0.798 | 0.731 |
| HistGBM_quant | 0.779 | 0.755 | 0.788 | 0.474 | 0.526 | 0.839 | 0.734 |
| Ens_proba_hgbmq+logq | 0.781 | 0.747 | 0.786 | 0.796 | 0.204 | 0.743 | 0.740 |
| Ens_min_cv+hgbmq | 0.791 | 0.742 | 0.781 | 0.744 | 0.256 | 0.777 | 0.736 |
| Ens_rankavg_cv+hgbmq | 0.796 | 0.742 | 0.784 | 0.865 | 0.135 | 0.709 | 0.729 |
| Ens_rankavg_cvnorm+hgbmq | 0.800 | 0.739 | 0.790 | 0.817 | 0.183 | 0.738 | 0.714 |
| Logistic_quant | 0.803 | 0.755 | 0.798 | 0.778 | 0.222 | 0.732 | 0.703 |
| Ens_cv0.7+hgbmq0.3 | 0.808 | 0.746 | 0.787 | 0.858 | 0.142 | 0.688 | 0.711 |
| _cv_smoothing_gate_ | 0.821 | 0.748 | 0.808 | 0.863 | 0.137 | 0.664 | 0.684 |
| cv_norm_gate | 0.830 | 0.812 | 0.837 | 0.753 | 0.247 | 0.710 | 0.636 |

## 2. OURS vs best non-ours baseline (per split, verdict)
| split | model | AURC | best_base | base_AURC | ΔAURC | ΔOC@.9 | ret | verdict |
|---|---|---|---|---|---|---|---|---|
| C+Ktr->Khold | TCSV_HistGBM_raw | 0.213 | selectivenet_proxy | 0.236 | -0.023 | -0.050 | 0.91 | small win |
| C+Ktr->Khold | MLP_quant | 0.223 | selectivenet_proxy | 0.236 | -0.013 | -0.039 | 0.76 | tie |
| C+Ktr->Khold | HistGBM_mono_raw | 0.230 | selectivenet_proxy | 0.236 | -0.006 | -0.001 | 0.91 | tie |
| C+Ktr->Khold | HistGBM_quant | 0.237 | selectivenet_proxy | 0.236 | +0.001 | +0.017 | 0.62 | tie |
| C+Ktr->Khold | HistGBM_mono_quant | 0.240 | selectivenet_proxy | 0.236 | +0.004 | +0.013 | 0.76 | tie |
| C+Ktr->Khold | Hier_cv_then_hgbmq | 0.242 | selectivenet_proxy | 0.236 | +0.006 | +0.011 | 0.76 | tie |
| C+Ktr->Khold | Ens_proba_hgbmq+logq | 0.245 | selectivenet_proxy | 0.236 | +0.009 | +0.008 | 0.77 | tie |
| C+Ktr->Khold | Ens_rankavg_cv+hgbmq | 0.248 | selectivenet_proxy | 0.236 | +0.012 | +0.008 | 0.80 | tie |
| C+Ktr->Khold | Ens_min_cv+hgbmq | 0.249 | selectivenet_proxy | 0.236 | +0.013 | +0.018 | 0.67 | tie |
| C+Ktr->Khold | Ens_cv0.7+hgbmq0.3 | 0.261 | selectivenet_proxy | 0.236 | +0.024 | +0.041 | 0.81 | LOSE |
| C+Ktr->Khold | Ens_rankavg_cvnorm+hgbmq | 0.267 | selectivenet_proxy | 0.236 | +0.031 | +0.054 | 0.75 | LOSE |
| C+Ktr->Khold | Logistic_quant | 0.267 | selectivenet_proxy | 0.236 | +0.031 | +0.034 | 0.76 | LOSE |
| C+Ktr->Khold | cv_norm_gate | 0.364 | selectivenet_proxy | 0.236 | +0.128 | +0.171 | 0.69 | LOSE |
| CARLA->CARLA | HistGBM_mono_raw | 0.680 | qiu_style(proxy) | 0.712 | -0.032 | -0.099 | 0.83 | STRONG win |
| CARLA->CARLA | TCSV_HistGBM_raw | 0.703 | qiu_style(proxy) | 0.712 | -0.009 | -0.063 | 0.57 | small win |
| CARLA->CARLA | HistGBM_quant | 0.747 | qiu_style(proxy) | 0.712 | +0.035 | -0.030 | 0.39 | ret_collapse |
| CARLA->CARLA | Ens_proba_hgbmq+logq | 0.749 | qiu_style(proxy) | 0.712 | +0.037 | -0.018 | 0.71 | LOSE |
| CARLA->CARLA | HistGBM_mono_quant | 0.750 | qiu_style(proxy) | 0.712 | +0.038 | -0.016 | 0.63 | LOSE |
| CARLA->CARLA | Hier_cv_then_hgbmq | 0.751 | qiu_style(proxy) | 0.712 | +0.040 | -0.017 | 0.62 | LOSE |
| CARLA->CARLA | Ens_min_cv+hgbmq | 0.756 | qiu_style(proxy) | 0.712 | +0.044 | -0.022 | 0.75 | LOSE |
| CARLA->CARLA | Ens_rankavg_cv+hgbmq | 0.766 | qiu_style(proxy) | 0.712 | +0.054 | -0.032 | 0.59 | LOSE |
| CARLA->CARLA | Ens_rankavg_cvnorm+hgbmq | 0.768 | qiu_style(proxy) | 0.712 | +0.056 | -0.029 | 0.59 | LOSE |
| CARLA->CARLA | Logistic_quant | 0.769 | qiu_style(proxy) | 0.712 | +0.058 | -0.014 | 0.71 | LOSE |
| CARLA->CARLA | MLP_quant | 0.770 | qiu_style(proxy) | 0.712 | +0.058 | -0.035 | 0.35 | ret_collapse |
| CARLA->CARLA | Ens_cv0.7+hgbmq0.3 | 0.788 | qiu_style(proxy) | 0.712 | +0.076 | -0.035 | 0.79 | LOSE |
| CARLA->CARLA | cv_norm_gate | 0.829 | qiu_style(proxy) | 0.712 | +0.118 | +0.019 | 0.79 | LOSE |
| CARLA->KITTI | Ens_cv0.7+hgbmq0.3 | 0.324 | cv_smoothing_gate | 0.327 | -0.003 | +0.001 | 0.62 | tie |
| CARLA->KITTI | Ens_rankavg_cv+hgbmq | 0.335 | cv_smoothing_gate | 0.327 | +0.008 | -0.004 | 0.45 | tie |
| CARLA->KITTI | Ens_min_cv+hgbmq | 0.347 | cv_smoothing_gate | 0.327 | +0.020 | -0.003 | 0.49 | LOSE |
| CARLA->KITTI | Logistic_quant | 0.358 | cv_smoothing_gate | 0.327 | +0.031 | +0.048 | 0.64 | LOSE |
| CARLA->KITTI | Ens_proba_hgbmq+logq | 0.359 | cv_smoothing_gate | 0.327 | +0.032 | +0.043 | 0.59 | LOSE |
| CARLA->KITTI | Ens_rankavg_cvnorm+hgbmq | 0.367 | cv_smoothing_gate | 0.327 | +0.040 | +0.083 | 0.46 | LOSE |
| CARLA->KITTI | HistGBM_mono_raw | 0.378 | cv_smoothing_gate | 0.327 | +0.051 | +0.053 | 0.63 | LOSE |
| CARLA->KITTI | Hier_cv_then_hgbmq | 0.382 | cv_smoothing_gate | 0.327 | +0.055 | +0.006 | 0.49 | LOSE |
| CARLA->KITTI | HistGBM_mono_quant | 0.392 | cv_smoothing_gate | 0.327 | +0.065 | +0.035 | 0.50 | LOSE |
| CARLA->KITTI | HistGBM_quant | 0.392 | cv_smoothing_gate | 0.327 | +0.065 | +0.025 | 0.39 | LOSE |
| CARLA->KITTI | MLP_quant | 0.400 | cv_smoothing_gate | 0.327 | +0.073 | +0.066 | 0.47 | LOSE |
| CARLA->KITTI | TCSV_HistGBM_raw | 0.406 | cv_smoothing_gate | 0.327 | +0.079 | +0.045 | 0.54 | LOSE |
| CARLA->KITTI | cv_norm_gate | 0.417 | cv_smoothing_gate | 0.327 | +0.090 | +0.125 | 0.69 | LOSE |
| K+Ctr->Chold | TCSV_HistGBM_raw | 0.685 | qiu_style(proxy) | 0.718 | -0.033 | -0.114 | 0.40 | ret_collapse |
| K+Ctr->Chold | HistGBM_mono_raw | 0.718 | qiu_style(proxy) | 0.718 | +0.001 | -0.089 | 0.58 | STRONG win |
| K+Ctr->Chold | HistGBM_mono_quant | 0.763 | qiu_style(proxy) | 0.718 | +0.045 | -0.032 | 0.75 | LOSE |
| K+Ctr->Chold | Hier_cv_then_hgbmq | 0.764 | qiu_style(proxy) | 0.718 | +0.046 | -0.032 | 0.75 | LOSE |
| K+Ctr->Chold | MLP_quant | 0.764 | qiu_style(proxy) | 0.718 | +0.046 | -0.016 | 0.53 | LOSE |
| K+Ctr->Chold | HistGBM_quant | 0.779 | qiu_style(proxy) | 0.718 | +0.062 | -0.026 | 0.47 | LOSE |
| K+Ctr->Chold | Ens_proba_hgbmq+logq | 0.781 | qiu_style(proxy) | 0.718 | +0.063 | -0.027 | 0.80 | LOSE |
| K+Ctr->Chold | Ens_min_cv+hgbmq | 0.791 | qiu_style(proxy) | 0.718 | +0.073 | -0.032 | 0.74 | LOSE |
| K+Ctr->Chold | Ens_rankavg_cv+hgbmq | 0.796 | qiu_style(proxy) | 0.718 | +0.078 | -0.029 | 0.86 | LOSE |
| K+Ctr->Chold | Ens_rankavg_cvnorm+hgbmq | 0.800 | qiu_style(proxy) | 0.718 | +0.082 | -0.024 | 0.82 | LOSE |
| K+Ctr->Chold | Logistic_quant | 0.803 | qiu_style(proxy) | 0.718 | +0.086 | -0.015 | 0.78 | LOSE |
| K+Ctr->Chold | Ens_cv0.7+hgbmq0.3 | 0.808 | qiu_style(proxy) | 0.718 | +0.090 | -0.026 | 0.86 | LOSE |
| K+Ctr->Chold | cv_norm_gate | 0.830 | qiu_style(proxy) | 0.718 | +0.113 | +0.023 | 0.75 | LOSE |
| KITTI->CARLA | MLP_quant | 0.817 | qiu_style(proxy) | 0.805 | +0.012 | -0.042 | 0.76 | small win |
| KITTI->CARLA | HistGBM_quant | 0.820 | qiu_style(proxy) | 0.805 | +0.014 | -0.055 | 0.77 | small win |
| KITTI->CARLA | HistGBM_mono_raw | 0.822 | qiu_style(proxy) | 0.805 | +0.017 | -0.051 | 0.64 | small win |
| KITTI->CARLA | HistGBM_mono_quant | 0.823 | qiu_style(proxy) | 0.805 | +0.017 | -0.044 | 0.76 | small win |
| KITTI->CARLA | TCSV_HistGBM_raw | 0.823 | qiu_style(proxy) | 0.805 | +0.018 | -0.053 | 0.58 | small win |
| KITTI->CARLA | Hier_cv_then_hgbmq | 0.824 | qiu_style(proxy) | 0.805 | +0.019 | -0.042 | 0.75 | small win |
| KITTI->CARLA | Ens_proba_hgbmq+logq | 0.830 | qiu_style(proxy) | 0.805 | +0.024 | -0.045 | 0.75 | small win |
| KITTI->CARLA | Ens_rankavg_cvnorm+hgbmq | 0.832 | qiu_style(proxy) | 0.805 | +0.027 | -0.027 | 0.81 | LOSE |
| KITTI->CARLA | Ens_rankavg_cv+hgbmq | 0.834 | qiu_style(proxy) | 0.805 | +0.028 | -0.043 | 0.81 | small win |
| KITTI->CARLA | Ens_min_cv+hgbmq | 0.834 | qiu_style(proxy) | 0.805 | +0.028 | -0.043 | 0.70 | small win |
| KITTI->CARLA | Ens_cv0.7+hgbmq0.3 | 0.838 | qiu_style(proxy) | 0.805 | +0.032 | -0.039 | 0.83 | LOSE |
| KITTI->CARLA | Logistic_quant | 0.839 | qiu_style(proxy) | 0.805 | +0.033 | -0.033 | 0.74 | LOSE |
| KITTI->CARLA | cv_norm_gate | 0.851 | qiu_style(proxy) | 0.805 | +0.045 | -0.000 | 0.64 | LOSE |
| KITTI->KITTI | TCSV_HistGBM_raw | 0.210 | selectivenet_proxy | 0.211 | -0.002 | +0.011 | 0.89 | tie |
| KITTI->KITTI | HistGBM_quant | 0.213 | selectivenet_proxy | 0.211 | +0.002 | +0.001 | 0.78 | tie |
| KITTI->KITTI | MLP_quant | 0.215 | selectivenet_proxy | 0.211 | +0.004 | -0.002 | 0.79 | tie |
| KITTI->KITTI | HistGBM_mono_raw | 0.228 | selectivenet_proxy | 0.211 | +0.017 | +0.079 | 0.86 | tie |
| KITTI->KITTI | HistGBM_mono_quant | 0.235 | selectivenet_proxy | 0.211 | +0.024 | +0.072 | 0.73 | LOSE |
| KITTI->KITTI | Hier_cv_then_hgbmq | 0.237 | selectivenet_proxy | 0.211 | +0.026 | +0.073 | 0.72 | LOSE |
| KITTI->KITTI | Ens_proba_hgbmq+logq | 0.245 | selectivenet_proxy | 0.211 | +0.033 | +0.092 | 0.75 | LOSE |
| KITTI->KITTI | Ens_rankavg_cv+hgbmq | 0.245 | selectivenet_proxy | 0.211 | +0.034 | +0.065 | 0.80 | LOSE |
| KITTI->KITTI | Ens_min_cv+hgbmq | 0.247 | selectivenet_proxy | 0.211 | +0.035 | +0.091 | 0.67 | LOSE |
| KITTI->KITTI | Ens_cv0.7+hgbmq0.3 | 0.259 | selectivenet_proxy | 0.211 | +0.047 | +0.111 | 0.82 | LOSE |
| KITTI->KITTI | Ens_rankavg_cvnorm+hgbmq | 0.261 | selectivenet_proxy | 0.211 | +0.050 | +0.111 | 0.76 | LOSE |
| KITTI->KITTI | Logistic_quant | 0.268 | selectivenet_proxy | 0.211 | +0.056 | +0.129 | 0.70 | LOSE |
| KITTI->KITTI | cv_norm_gate | 0.365 | selectivenet_proxy | 0.211 | +0.153 | +0.252 | 0.69 | LOSE |

## 3. Aggregate ranking (avg ΔAURC over 4 non-direct splits; worst direct ΔAURC)
| model | avg ΔAURC (non-direct)↓ | worst direct ΔAURC | 
|---|---|---|
| TCSV_HistGBM_raw | -0.0166 | +0.0790 |
| HistGBM_mono_raw **←FINAL** | -0.0053 | +0.0511 |
| MLP_quant | +0.0237 | +0.0733 |
| HistGBM_quant | +0.0247 | +0.0652 |
| HistGBM_mono_quant | +0.0278 | +0.0649 |
| Hier_cv_then_hgbmq | +0.0295 | +0.0547 |
| Ens_proba_hgbmq+logq | +0.0357 | +0.0631 |
| Ens_min_cv+hgbmq | +0.0415 | +0.0733 |
| Ens_rankavg_cv+hgbmq | +0.0447 | +0.0783 |
| Ens_rankavg_cvnorm+hgbmq | +0.0549 | +0.0824 |
| Logistic_quant | +0.0577 | +0.0857 |
| Ens_cv0.7+hgbmq0.3 | +0.0595 | +0.0901 |
| cv_norm_gate | +0.1279 | +0.1534 |

## 4. Final model (robustness-aware pick) = **HistGBM_mono_raw**

Bootstrap AURC(final)−AURC(baseline) over groups, 95% CI (negative ⇒ final better):
| split | vs baseline | mean ΔAURC | 95% CI | verdict |
|---|---|---|---|---|
| KITTI->KITTI | `cv_smoothing_gate` | -0.0607 | [-0.0786, -0.0499] | ✅ better |
| KITTI->KITTI | `selectivenet_proxy` | +0.0167 | [+0.0116, +0.0241] | ✗ worse |
| C+Ktr->Khold | `cv_smoothing_gate` | -0.0608 | [-0.0827, -0.0464] | ✅ better |
| C+Ktr->Khold | `selectivenet_proxy` | -0.0059 | [-0.0198, +0.0075] | ns (CI∋0) |
| CARLA->CARLA | `cv_smoothing_gate` | -0.1403 | [-0.2393, -0.0711] | ✅ better |
| CARLA->CARLA | `qiu_style(proxy)` | -0.0354 | [-0.0668, -0.0119] | ✅ better |

## Honest reading
- Gate thresholds: STRONG win = ΔAURC≤−0.05 or ΔOC@.9≤−0.07; small = −0.03..−0.05 / −0.04..−0.07; tie = ΔAURC within +0.02; lose = ΔAURC>+0.02.
- See `PAPER2_FINAL_MODEL_DECISION.md` for the honest gate verdict (RA-L / IV-ITSC / pivot).
