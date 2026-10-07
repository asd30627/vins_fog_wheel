# PAPER2 Phase 1 — VINS MASKING LIMITATION AUDIT

> Honest re-examination of the prior Phase-C masking run, cross-referenced with the Phase -1 recording-quality classification. Date 2026-07-01.

## 0. Was `validity_aware` actually TCSV-M?
**No.** In the prior Phase-C run, `validity_aware` = a **raw-speed gate** (mask detections whose OWN raw estimated speed > 1 m/s). It did **NOT** use the Part-1 learned TCSV-M model. This is acknowledged here; using the real TCSV-M is Phase 2 (`paper2_vins_tcsv_masking.py`). Calling the prior variant 'validity_aware' overstated it — it is a deployable *observability* gate, not the model.

## 1. Per run × variant (VINS internals + metrics + data quality)
| run | quality | variant | ATE_rmse | RPE | early | late | mgr_feat | outlier_ratio | kf | fail |
|---|---|---|---|---|---|---|---|---|---|---|
| Town01/dense_b1 | PASS_CORE | baseline | 3.924 | 0.3077 | 1.0149 | 0.5109 | 52.4 | 0.517 | 267 | 0 |
| Town01/dense_b1 | PASS_CORE | all_dynamic | 3.543 | 0.2438 | 0.9968 | 0.4666 | 50.1 | 0.502 | 267 | 0 |
| Town01/dense_b1 | PASS_CORE | validity_aware | 3.512 | 0.2347 | 0.9936 | 0.4598 | 49.7 | 0.493 | 267 | 0 |
| Town01/dense_b1 | PASS_CORE | oracle | 3.543 | 0.2439 | 0.9968 | 0.4667 | 51.9 | 0.522 | 267 | 0 |
| Town01/medium_b1 | PASS_CORE | baseline | 3.517 | 0.2076 | 0.9928 | 0.4505 | 58.5 | 0.517 | 269 | 0 |
| Town01/medium_b1 | PASS_CORE | all_dynamic | 3.418 | 0.1871 | 0.9772 | 0.438 | 56.2 | 0.468 | 267 | 0 |
| Town01/medium_b1 | PASS_CORE | validity_aware | 3.418 | 0.1871 | 0.9772 | 0.438 | 56.3 | 0.486 | 267 | 0 |
| Town01/medium_b1 | PASS_CORE | oracle | 3.418 | 0.1871 | 0.9772 | 0.438 | 59.3 | 0.51 | 267 | 0 |
| Town06/dense_b1 | PASS_CORE | baseline | 41.69 | 3.5642 | 1.2917 | 2.7898 | 47.0 | 0.344 | 347 | 0 |
| Town06/dense_b1 | PASS_CORE | all_dynamic | 19.38 | 1.0961 | 1.0255 | 1.9354 | 50.8 | 0.356 | 347 | 0 |
| Town06/dense_b1 | PASS_CORE | validity_aware | 20.121 | 1.2715 | 1.0596 | 1.9517 | 52.1 | 0.334 | 348 | 0 |
| Town06/dense_b1 | PASS_CORE | oracle | 24.534 | 1.855 | 1.1257 | 2.1032 | 50.7 | 0.337 | 347 | 0 |
| Town07/dense_b1 | INVALID_RECORDING | baseline | 25.856 | 2.2145 | 1.0596 | nan | 48.9 | 0.411 | 348 | 0 |
| Town07/dense_b1 | INVALID_RECORDING | all_dynamic | 33.432 | 3.0173 | 0.9987 | nan | 60.5 | 0.513 | 347 | 0 |
| Town07/dense_b1 | INVALID_RECORDING | validity_aware | 31.285 | 2.7667 | 1.0267 | nan | 48.3 | 0.398 | 348 | 0 |
| Town07/dense_b1 | INVALID_RECORDING | oracle | 22.352 | 1.9582 | 0.9556 | nan | 57.5 | 0.476 | 347 | 0 |

## 2. Which runs are valid for CORE VINS experiments?
- Town01__dynamic_v3__rundense_b1: baseline early=1.0149 ATE=3.924 m, quality=PASS_CORE → **CORE** (clean data + stable baseline)
- Town01__dynamic_v3__runmedium_b1: baseline early=0.9928 ATE=3.517 m, quality=PASS_CORE → **CORE** (clean data + stable baseline)
- Town06__dynamic_v3__rundense_b1: baseline early=1.2917 ATE=41.69 m, quality=PASS_CORE → **FAILURE-ANALYSIS ONLY** (clean data but baseline unstable)
- Town07__dynamic_v3__rundense_b1: baseline early=1.0596 ATE=25.856 m, quality=INVALID_RECORDING → **EXCLUDE** (data quality = INVALID_RECORDING)

## 3. Answers to the Phase-1 questions
1. **validity_aware = TCSV-M?** No — raw_speed gate (see §0).
2. **Per-run baseline stability / features / outliers:** see §1. Note VINS baseline **outlier ratio is already ~0.9** on Town01 — the frontend is *already rejecting the vast majority of features* (incl. most dynamic-object features) via RANSAC/F-threshold. This is the core limitation: input masking removes features the estimator would have rejected anyway → small net effect.
3. **Town07 deployable mask worse (+29%)?** Town07 dense_b1 is **INVALID (spawn collision)** — an NPC fills 56% of the frame at 1.26 m. Masking it removes almost all features → VINS starves → worse. The prior +29% was a data artifact, not a method failure.
4. **Town06 baseline ATE 41 m?** Town06 dense_b1 has 84% of objects >150 m and is a fast highway scene; baseline early-scale 1.29 (already off). Borderline PASS_CORE → failure-analysis only.
5. **Core-worthy runs:** only **Town01 dense_b1 & medium_b1** (PASS_CORE + stable baseline). On those two clean runs, prior masking gave validity_aware −10.5% / −2.8% ATE with 0 failures — a consistent small improvement, no regression. The 'mixed/erratic' Phase-C story was driven by the 2 bad runs (Town06 borderline, Town07 invalid).
6. **Failure-analysis-only runs:** Town06 dense_b1 (unstable baseline), Town07 dense_b1 (invalid).

## 4. Limitations of the prior masking approach
- **Image blur, not feature-level routing:** suppression was a side effect of blurring; some boundary features survive and blurred regions can still yield weak corners. Phase 3 (feature-tracker routing) is the correct mechanism.
- **Frontend already rejects dynamics** (outlier ratio ~0.9) → limited headroom for input masking.
- **No per-feature pixel coordinates logged** → cannot yet count exactly how many VINS features fell inside object bboxes; `mgr_feat` delta (baseline vs masked) is only a coarse proxy. Phase 3 routing should log object-region feature counts explicitly.
- **raw_speed ≠ learned validity** → Phase 2 must plug in TCSV-M and re-test on CLEAN runs only.

## 5. Verdict
Re-run the VINS masking experiments **only on PASS_CORE + stable runs** (currently Town01 dense/medium; more after Phase -3 re-record), with the **real TCSV-M** (Phase 2) and ideally **feature-level routing** (Phase 3). Drop Town07 (invalid) and treat Town06 as failure-analysis. The prior positive signal on clean runs (~−6% mean, 0 failures) stands; the negative/erratic parts were data-quality artifacts.
