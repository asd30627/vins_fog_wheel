# PAPER2_V5_OBJECT_CONSISTENCY_EGO_DIAGNOSTIC (C4, optional)

> OFFLINE correlation: does per-frame object-motion inconsistency track VINS degradation? NO VINS feedback, NO object factor, NO localization claim.

- frames analyzed (>=2 objects): 4377

## Frame-level Spearman correlations
- obj_speed_err_mean vs vins_outlier_ratio: rho=-0.045 p=0.0027 n=4377 -> **null (rho=-0.05, p=0.0027)**
- obj_speed_err_mean vs (-vins_feat_count): rho=-0.003 p=0.86 n=4377 -> **null (rho=-0.00, p=0.86)**
- obj_raw_speed_std vs vins_outlier_ratio: rho=-0.032 p=0.034 n=4377 -> **null (rho=-0.03, p=0.034)**

## Recording-level: mean object speed error vs VINS scale divergence
- rho=nan p=nan n=19 -> **null (insufficient)**

```
                            recname  speed_err_ms  scale
    Town01__dynamic_v3__rundense_b1         19.30   0.89
   Town01__dynamic_v3__rundense_r30         33.13   2.80
   Town01__dynamic_v3__rundense_r60         14.84   1.25
   Town01__dynamic_v3__rundense_r90         55.75   1.67
   Town01__dynamic_v3__runmedium_b1         11.98   0.82
  Town01__dynamic_v3__runmedium_r30          7.04   0.92
  Town01__dynamic_v3__runmedium_r60         49.54   1.26
  Town01__dynamic_v3__runmedium_r90         79.27   2.44
  Town01__dynamic_v3__runsparse_r30         10.52   0.77
  Town01__dynamic_v3__runsparse_r60         53.00   1.26
  Town10HD__dynamic_v3__rundense_b1         76.37   5.08
 Town10HD__dynamic_v3__rundense_r30         53.47   2.82
 Town10HD__dynamic_v3__rundense_r60         35.44   1.14
 Town10HD__dynamic_v3__rundense_r90         37.02   1.61
 Town10HD__dynamic_v3__runmedium_b1         11.80   1.64
Town10HD__dynamic_v3__runmedium_r30         12.95   3.36
Town10HD__dynamic_v3__runmedium_r90         58.89   1.63
 Town10HD__dynamic_v3__runsparse_b1        152.15   2.44
Town10HD__dynamic_v3__runsparse_r90         42.39   1.60
```

## Conclusion (honest)
- strongest signal |rho| ≈ 0.05 -> diagnostic = **null/weak**.
- object-motion inconsistency as an INDEPENDENT ego-degradation alert: is weak/inconclusive here — report as a minor/negative finding, do not package.
- caveat: VINS scale divergence here is partly artifact of aggressive 640 recordings; object speed error also driven by range/observability, confounding the ego-degradation link.
