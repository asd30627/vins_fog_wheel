# PAPER2_OBJECT_VINS_JOIN_REPORT

> Join VINS reliability features to 20921 object detections by nearest timestamp (max_dt 0.15s).
> Overall VINS match rate: **19941/20921 (0.953)**.

## Per-recording match
| reliability_tag | obj_det | matched | rel_rows |
|---|---|---|---|
| rep_dense_b1_Town01 | 1291 | 1271 | 267 |
| rep_dense_b1_Town10HD | 2273 | 2192 | 269 |
| rep_dense_r30_Town01 | 1143 | 1085 | 267 |
| rep_dense_r30_Town10HD | 2126 | 2007 | 267 |
| rep_dense_r60_Town01 | 1293 | 1241 | 267 |
| rep_dense_r60_Town10HD | 702 | 682 | 269 |
| rep_dense_r90_Town01 | 565 | 520 | 267 |
| rep_dense_r90_Town10HD | 1834 | 1765 | 267 |
| rep_medium_b1_Town01 | 1094 | 1094 | 268 |
| rep_medium_b1_Town10HD | 1081 | 1058 | 269 |
| rep_medium_r30_Town01 | 706 | 660 | 267 |
| rep_medium_r30_Town10HD | 1298 | 1227 | 267 |
| rep_medium_r60_Town01 | 661 | 619 | 267 |
| rep_medium_r60_Town10HD | 272 | 249 | 267 |
| rep_medium_r90_Town01 | 364 | 318 | 267 |
| rep_medium_r90_Town10HD | 1086 | 1042 | 269 |
| rep_sparse_b1_Town01 | 6 | 6 | 267 |
| rep_sparse_b1_Town10HD | 852 | 816 | 267 |
| rep_sparse_r30_Town01 | 5 | 5 | 267 |
| rep_sparse_r30_Town10HD | 453 | 407 | 267 |
| rep_sparse_r60_Town01 | 1025 | 974 | 267 |
| rep_sparse_r60_Town10HD | 278 | 255 | 267 |
| rep_sparse_r90_Town01 | 5 | 5 | 268 |
| rep_sparse_r90_Town10HD | 508 | 443 | 267 |

## Notes
- recordings with 0 VINS match: none (VINS replay missing/failed or ts disjoint).
- VINS quality cols joined: vins_feat_count, vins_feat_raw, vins_outlier_ratio, vins_inlier, vins_coverage8, vins_entropy8, vins_track_len, vins_solver_ms, vins_gyro_vins_diff, vins_depth_mean, vins_depth_std, vins_good_depth, vins_bad_depth, vins_vel_norm, vins_ba_norm, vins_bg_norm, vins_gyr_z_std, vins_failure
- matched rows carry deployable VINS localization-quality features for the A2 conditioning test.
