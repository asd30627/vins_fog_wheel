# PAPER2_CALIBRATION_RESULTS

> Is the TCSV validity score a usable probability for refusal thresholding? ECE (15-bin), Brier, reliability diagrams; Platt/isotonic fit on a held-out calibration split (by run/seq, no leak).

| dataset | model | ECE_raw | ECE_platt | ECE_isotonic | Brier_raw | Brier_platt | Brier_isotonic |
|---|---|---|---|---|---|---|---|
| CARLA | TCSV-HistGBM | 0.031 | 0.098 | 0.058 | 0.092 | 0.111 | 0.105 |
| CARLA | TCSV-MLP | 0.042 | 0.056 | 0.038 | 0.100 | 0.107 | 0.106 |
| KITTI | TCSV-HistGBM | 0.020 | 0.051 | 0.040 | 0.107 | 0.110 | 0.111 |
| KITTI | TCSV-MLP | 0.019 | 0.040 | 0.019 | 0.118 | 0.120 | 0.119 |

## Reading
- Lower ECE/Brier = better-calibrated. If isotonic/Platt clearly lowers ECE, deploy the calibrated score and pick the refusal threshold on the calibrated probability.
- AURC/AUROC are rank metrics and are unchanged by monotone calibration; calibration matters for choosing an interpretable operating threshold, not for ranking.
- Figure: figs/fig_tcsv_reliability.png
