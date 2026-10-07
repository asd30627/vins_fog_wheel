# PAPER2_OBJECT_VINS_JOIN_REPORT

> Join VINS reliability features to 30102 object detections by nearest timestamp (max_dt 0.15s).
> Overall VINS match rate: **19941/30102 (0.662)**.

## Per-recording match
| reliability_tag | obj_det | matched | rel_rows |
|---|---|---|---|
| rep_dense_b1_Town01 | 1291 | 1271 | 267 |
| rep_dense_b1_Town06 | 856 | 0 | 0 |
| rep_dense_b1_Town07 | 864 | 0 | 0 |
| rep_dense_b1_Town10HD | 2273 | 2192 | 269 |
| rep_dense_r30_Town01 | 1143 | 1085 | 267 |
| rep_dense_r30_Town06 | 541 | 0 | 0 |
| rep_dense_r30_Town07 | 6 | 0 | 0 |
| rep_dense_r30_Town10HD | 2126 | 2007 | 267 |
| rep_dense_r60_Town01 | 1293 | 1241 | 267 |
| rep_dense_r60_Town06 | 327 | 0 | 0 |
| rep_dense_r60_Town07 | 844 | 0 | 0 |
| rep_dense_r60_Town10HD | 702 | 682 | 269 |
| rep_dense_r90_Town01 | 565 | 520 | 267 |
| rep_dense_r90_Town06 | 3 | 0 | 0 |
| rep_dense_r90_Town07 | 935 | 0 | 0 |
| rep_dense_r90_Town10HD | 1834 | 1765 | 267 |
| rep_medium_b1_Town01 | 1094 | 1094 | 268 |
| rep_medium_b1_Town06 | 881 | 0 | 0 |
| rep_medium_b1_Town07 | 349 | 0 | 0 |
| rep_medium_b1_Town10HD | 1081 | 1058 | 269 |
| rep_medium_r30_Town01 | 706 | 660 | 267 |
| rep_medium_r30_Town06 | 727 | 0 | 0 |
| rep_medium_r30_Town07 | 44 | 0 | 0 |
| rep_medium_r30_Town10HD | 1298 | 1227 | 267 |
| rep_medium_r60_Town01 | 661 | 619 | 267 |
| rep_medium_r60_Town06 | 7 | 0 | 0 |
| rep_medium_r60_Town07 | 338 | 0 | 0 |
| rep_medium_r60_Town10HD | 272 | 249 | 267 |
| rep_medium_r90_Town01 | 364 | 318 | 267 |
| rep_medium_r90_Town06 | 3 | 0 | 0 |
| rep_medium_r90_Town07 | 545 | 0 | 0 |
| rep_medium_r90_Town10HD | 1086 | 1042 | 269 |
| rep_sparse_b1_Town01 | 6 | 6 | 267 |
| rep_sparse_b1_Town06 | 1270 | 0 | 0 |
| rep_sparse_b1_Town07 | 195 | 0 | 0 |
| rep_sparse_b1_Town10HD | 852 | 816 | 267 |
| rep_sparse_r30_Town01 | 5 | 5 | 267 |
| rep_sparse_r30_Town07 | 20 | 0 | 0 |
| rep_sparse_r30_Town10HD | 453 | 407 | 267 |
| rep_sparse_r60_Town01 | 1025 | 974 | 267 |
| rep_sparse_r60_Town06 | 6 | 0 | 0 |
| rep_sparse_r60_Town07 | 5 | 0 | 0 |
| rep_sparse_r60_Town10HD | 278 | 255 | 267 |
| rep_sparse_r90_Town01 | 5 | 5 | 268 |
| rep_sparse_r90_Town06 | 6 | 0 | 0 |
| rep_sparse_r90_Town07 | 409 | 0 | 0 |
| rep_sparse_r90_Town10HD | 508 | 443 | 267 |

## Notes
- recordings with 0 VINS match: ['rep_dense_b1_Town06', 'rep_dense_r30_Town06', 'rep_dense_r60_Town06', 'rep_dense_r90_Town06', 'rep_medium_b1_Town06', 'rep_medium_r30_Town06', 'rep_medium_r60_Town06', 'rep_medium_r90_Town06', 'rep_sparse_b1_Town06', 'rep_sparse_r60_Town06', 'rep_sparse_r90_Town06', 'rep_dense_b1_Town07', 'rep_dense_r30_Town07', 'rep_dense_r60_Town07', 'rep_dense_r90_Town07', 'rep_medium_b1_Town07', 'rep_medium_r30_Town07', 'rep_medium_r60_Town07', 'rep_medium_r90_Town07', 'rep_sparse_b1_Town07', 'rep_sparse_r30_Town07', 'rep_sparse_r60_Town07', 'rep_sparse_r90_Town07'] (VINS replay missing/failed or ts disjoint).
- VINS quality cols joined: vins_feat_count, vins_feat_raw, vins_outlier_ratio, vins_inlier, vins_coverage8, vins_entropy8, vins_track_len, vins_solver_ms, vins_gyro_vins_diff, vins_depth_mean, vins_depth_std, vins_good_depth, vins_bad_depth, vins_vel_norm, vins_ba_norm, vins_bg_norm, vins_gyr_z_std, vins_failure
- matched rows carry deployable VINS localization-quality features for the A2 conditioning test.
