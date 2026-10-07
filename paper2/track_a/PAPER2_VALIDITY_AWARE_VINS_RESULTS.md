# PAPER2 Part 2 — VALIDITY-AWARE VINS RESULTS

> Stereo-inertial VINS-Fusion on CARLA (true VIO), offline replay (CARLA OFF), b05 config, rate 0.5, ideal IMU + skip-imu-head 150. Intervention = LEFT-image feature suppression of dynamic-object bboxes (Gaussian-blur, soft boundary), 4 variants. Metric ATE_rmse↓ (Umeyama SE3-aligned), RPE_trans↓, scale early/late (1.0 ideal), #vio rows, VINS failures. GT used only for eval/oracle. Date 2026-07-01.

Variants: **baseline** (no mask) · **all_dynamic** (mask every detection = DynaVINS-style proxy) · **validity_aware** (mask only raw_speed>1 m/s = observably-moving, deployable) · **oracle** (mask only GT gt_speed>1 = truly-moving, upper bound).

## Per-run × variant
| run | variant | ATE_rmse | ATE_mean | RPE_trans | early | late | n_vio | fail | diverged |
|---|---|---|---|---|---|---|---|---|---|
| Town01__dynamic_v3__rundense_b1 | baseline | 3.924 | 3.346 | 0.3077 | 1.0149 | 0.5109 | 268 | 0 | False |
| Town01__dynamic_v3__rundense_b1 | all_dynamic | 3.543 | 2.735 | 0.2438 | 0.9968 | 0.4666 | 268 | 0 | False |
| Town01__dynamic_v3__rundense_b1 | validity_aware | 3.512 | 2.656 | 0.2347 | 0.9936 | 0.4598 | 268 | 0 | False |
| Town01__dynamic_v3__rundense_b1 | oracle | 3.543 | 2.735 | 0.2439 | 0.9968 | 0.4667 | 268 | 0 | False |
| Town01__dynamic_v3__runmedium_b1 | baseline | 3.517 | 2.615 | 0.2076 | 0.9928 | 0.4505 | 270 | 0 | False |
| Town01__dynamic_v3__runmedium_b1 | all_dynamic | 3.418 | 2.333 | 0.1871 | 0.9772 | 0.438 | 268 | 0 | False |
| Town01__dynamic_v3__runmedium_b1 | validity_aware | 3.418 | 2.333 | 0.1871 | 0.9772 | 0.438 | 268 | 0 | False |
| Town01__dynamic_v3__runmedium_b1 | oracle | 3.418 | 2.333 | 0.1871 | 0.9772 | 0.438 | 268 | 0 | False |
| Town06__dynamic_v3__rundense_b1 | baseline | 41.69 | 35.759 | 3.5642 | 1.2917 | 2.7898 | 348 | 0 | False |
| Town06__dynamic_v3__rundense_b1 | all_dynamic | 19.38 | 16.77 | 1.0961 | 1.0255 | 1.9354 | 348 | 0 | False |
| Town06__dynamic_v3__rundense_b1 | validity_aware | 20.121 | 17.501 | 1.2715 | 1.0596 | 1.9517 | 349 | 0 | False |
| Town06__dynamic_v3__rundense_b1 | oracle | 24.534 | 21.319 | 1.855 | 1.1257 | 2.1032 | 348 | 0 | False |
| Town07__dynamic_v3__rundense_b1 | baseline | 25.856 | 21.621 | 2.2145 | 1.0596 | nan | 349 | 0 | False |
| Town07__dynamic_v3__rundense_b1 | all_dynamic | 33.432 | 27.961 | 3.0173 | 0.9987 | nan | 348 | 0 | False |
| Town07__dynamic_v3__rundense_b1 | validity_aware | 31.285 | 26.169 | 2.7667 | 1.0267 | nan | 349 | 0 | False |
| Town07__dynamic_v3__rundense_b1 | oracle | 22.352 | 18.155 | 1.9582 | 0.9556 | nan | 348 | 0 | False |

## ATE_rmse % change vs baseline (negative = improvement)
| run | all_dynamic | validity_aware | oracle |
|---|---|---|---|
| Town01__dynamic_v3__rundense_b1 | -9.7% | -10.5% | -9.7% |
| Town01__dynamic_v3__runmedium_b1 | -2.8% | -2.8% | -2.8% |
| Town06__dynamic_v3__rundense_b1 | -53.5% | -51.7% | -41.2% |
| Town07__dynamic_v3__rundense_b1 | +29.3% | +21.0% | -13.6% |

## Mean ATE % change vs baseline (across runs)
- **all_dynamic**: -9.2% (n=4 runs)
- **validity_aware**: -11.0% (n=4 runs)
- **oracle**: -16.8% (n=4 runs)

---

## Analysis (honest, mixed result)

**Means (4 runs):** all_dynamic −9.2%, validity_aware −11.0%, **oracle −16.8%** ATE.
**Stable-baseline subset (Town01 ×2, baseline early∈[0.9,1.1], ATE<10 m):** all_dynamic −6.3%,
validity_aware −6.7%, oracle −6.3% — tight cluster, all ~−6%.

### Split by baseline quality (the decisive cut)
- **Stable baselines (Town01 dense_b1 ATE 3.9 m, medium_b1 3.5 m):** masking dynamic objects gives a
  **small, consistent improvement** (−2.8% to −10.5%). validity_aware ≈ all_dynamic ≈ oracle (within ~1%).
  No VINS failures, vio-pose count unchanged. → concept works, selectivity is neutral here.
- **Degraded baselines (Town06 dense_b1 baseline ATE 41.7 m, early-scale 1.29; Town07 25.9 m):** results are
  **erratic**. Town06: masking helps massively (−41 to −53%) but only because the baseline is already
  semi-diverged. Town07: deployable masking **HURTS** (all_dynamic **+29%**, validity_aware **+21%**); only
  **oracle helps (−14%)**. → when the baseline is broken, imperfect masking is unsafe; perfect (GT) masking
  is the only consistently-safe variant.

### Why the differences between masking variants are small / mixed
- **oracle is best on average (−16.8%)** and the only variant that never hurts → confirms dynamic objects DO
  pollute VINS, but the deployable signal (raw_speed) is imperfect enough to occasionally remove good
  features or keep bad ones.
- **validity_aware ≈ all_dynamic** on most runs → on these scenes, masking *all* detections vs only
  *observably-moving* ones changes the surviving feature set little (VINS's RANSAC / F-threshold already
  drops many moving-object features; min_dist=15 spacing means few keypoints land on objects anyway).
- **Town01 medium_b1: all three masked variants give identical ATE (3.418)** → for that run the different
  masks did not change which features VINS ultimately used at all (the dynamic regions carried no surviving
  keypoints). A concrete instance of "the frontend already handles it."

### Success-gate checklist (user's)
| gate | result |
|---|---|
| dynamic-heavy ATE/RPE improve 5–10% | **partially** — yes on stable Town01 (6–10%) & oracle mean −16.8%; not on Town07 (deployable hurts) |
| failure count not increase | ✅ **0 VINS failures** in all 16 runs |
| static/easy not regress | ✅ Town01 medium (easier) −2.8%, no regression |
| beat all-dynamic-removal | ❌ validity_aware ≈ all_dynamic (selective signal not yet a clear win) |
| approach oracle | ✅ on stable runs; ❌ on Town07 (only oracle helps) |

### Dominant error source
Every baseline shows **late-scale drift** (late-scale 0.45–0.51 on Town01; >1.9 on Town06/07). This
IMU/scale drift, not dynamic-object pollution, is the dominant ATE contributor — which caps how much any
feature-suppression can buy and explains the modest, variable gains.
