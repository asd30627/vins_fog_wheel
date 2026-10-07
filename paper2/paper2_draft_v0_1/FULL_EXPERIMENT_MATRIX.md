# FULL EXPERIMENT MATRIX — Paper-2 Draft v0.1

> Single source of truth for what was run, with which split, which metric, and where the artifact lives.
> Status: ✅ done this round · 🟡 partial · ⬜ todo. Splits never frame-random.

## 1. Models / baselines × splits (selective-risk suite)
Artifact: `PAPER2_PUBLIC_PROXY_BASELINE_RESULTS.md` + `paper2_public_proxy_baselines_metrics.csv`. Metrics:
AUROC, AURC↓, overconf, overconf@ret.8, overconf@ret.9, retention, false_refusal, F1_invalid.

| model | CARLA→CARLA | KITTI→KITTI | CARLA→KITTI | KITTI→CARLA | C+Ktr→K-hold | K+Ctr→C-hold |
|---|---|---|---|---|---|---|
| no_policy | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| distance_gate | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| qiu_style(proxy) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| yolo_conf_gate | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| bbox_depth_gate | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| cv_smoothing_gate | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| ovi_geom | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| selectivenet_proxy | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| TCSV-rule | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| TCSV-HistGBM | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| TCSV-MLP | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

**AURC↓ headline (TCSV-HistGBM vs best non-ours baseline):**
| split | TCSV | best baseline | Δ |
|---|---|---|---|
| CARLA→CARLA | 0.703 | qiu 0.712 | −0.009 ✅ |
| KITTI→KITTI | 0.210 | cv_smoothing 0.288 | −0.078 ✅ |
| CARLA→KITTI | 0.406 | cv_smoothing 0.327 | +0.079 ❌ |
| KITTI→CARLA | 0.823 | qiu 0.805 | +0.018 ❌ |
| C+Ktr→K-hold | 0.213 | selnet 0.236 | −0.023 ✅ |
| K+Ctr→C-hold | 0.685 | qiu 0.718 | −0.033 ✅ |

## 2. Phenomenon (C1)
| experiment | split/scope | metric | status | artifact |
|---|---|---|---|---|
| validity-by-range | CARLA & KITTI bins | pos/vel valid by bin | ✅ | `PAPER2_KITTI_TRACKING_VALIDITY_RESULTS.md` |
| threshold robustness (regrouped) | pos×vel τ, in-domain | R1–R4 + TCSV-vs-distance | ✅ 14/18 + 6/6 | `PAPER2_THRESHOLD_ROBUSTNESS_REGROUPED.md` |
| collision/near-contact audit | 24 CARLA runs | near-contact frame % | ✅ 3.8% | `PAPER2_CARLA_COLLISION_AUDIT.md` |

## 3. Method analyses
| experiment | metric | status | artifact |
|---|---|---|---|
| new-residual vs OLD10 | AUROC/AURC | ✅ (net neutral) | `PAPER2_TCSV_RESULTS.md` §2 |
| permutation importance | ΔAUROC by group/feature | ✅ | `paper2_tcsv_importance.csv` |
| SHAP figure | per-feature | ⬜ (needs shap) | `[TODO P1-3]` |
| temporal-window ablation | AUROC/AURC W∈{1,3,5,7} | ✅ | `paper2_tcsv_window_ablation.csv` |
| leakage audit | provenance + controls | ✅ | `PAPER2_LEAKAGE_AUDIT.md` |
| calibration | ECE/Brier/reliability/Platt/isotonic | ✅ | `PAPER2_CALIBRATION_RESULTS.md` |

## 4. Planner-facing (C3)
| experiment | dataset | metric | status | artifact |
|---|---|---|---|---|
| TTC false-alarm/missed-risk/overconf-accepted | CARLA front | rates vs coverage | ✅ | `PAPER2_PLANNER_TTC_RESULTS.md` |
| KITTI TTC | KITTI | same | ⬜ (needs GT range) | `[TODO P1-1]` |
| position-only TTC fallback | both | recovered safe decisions | ⬜ | `[TODO P1-1]` |

## 5. Regimes / qualitative
| experiment | status | artifact |
|---|---|---|
| failure gallery (data-driven) | 🟡 | `PAPER2_FAILURE_GALLERY.md` + `figs/failure_gallery/` |
| representative frames | ⬜ | `[TODO P1-2]` (no tracking images in workspace) |

## 6. Not yet started (P2)
runtime/latency table ⬜ · third-dataset feasibility ⬜ · bootstrap CIs ⬜ · full retention/threshold sweep 🟡.

## Scripts inventory (all standalone, no backend)
- `scripts/paper2_tcsv_features.py` (feature module, grouping fix)
- `scripts/paper2_tcsv_train_eval.py` (TCSV models + ablations + importance + window)
- `scripts/paper2_public_proxy_baselines.py` (Part C)
- `scripts/paper2_leakage_audit.py`, `paper2_threshold_robustness_regrouped.py`,
  `paper2_calibration_eval.py`, `paper2_planner_ttc_eval.py`, `paper2_failure_gallery.py` (Part D)
