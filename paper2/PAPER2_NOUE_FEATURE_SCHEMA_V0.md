# PAPER2_NOUE_FEATURE_SCHEMA_V0 — Workstream D

> Change: paper2-noue-g0-data-grounding。2026-06-30。
> NOUE conditioning 的 **v0 feature schema**，**只用現有 `reliability_features_vins.csv` 既有欄位**（G0 不補 estimator logging）。

## 來源（實測）
- `reliability_features_vins.csv`（schema v3，156 欄/keyframe ~10Hz；部署即時可得）。
- 驗證樣本：`/mnt/sata4t/ivlab3_data/fwvio/results/kitti/drive0018/reliability_features_vins.csv`（156 欄、2751 列、timestamp 1.147→287.641 s）。
- 聚合版參考：`kaist_grade_scripts/reliability_dataset.tsv`（22028 列，5s-window）。

## v0 conditioning feature schema（對齊實際欄位，皆現成）

| v0 feature | reliability CSV 欄位（col idx 實測）| 說明 |
|---|---|---|
| timestamp | `timestamp` (7) | 對齊鍵（秒）|
| feature_count | `tracked_feature_count_raw` (16), `tracked_feature_count_mgr` (17) | 前端/後端追蹤特徵數 |
| outlier_ratio | `outlier_ratio_last` (34) | 後端外點比例 |
| coverage | `coverage_8x8` (25)（另 `coverage_4x4` 24）| 特徵空間覆蓋 |
| track_length | `avg_track_length` (128) | 平均追蹤長度 |
| solver_time | `solver_time_ms_last` (31) | 後端求解時間 |
| failure_proxy | `failure_detected_last` (35), `failure_reason_proxy` (36) | 失敗旗標/原因 |
| gyr_z_mean/std（yaw rate）| `gyr_z_mean` (80), `gyr_z_std` (83) | yaw 角速度 |
| gyro_vins_so3_diff_deg | `gyro_vins_so3_diff_deg` (106) | gyro–vision 旋轉分歧（核心 conditioning 訊號）|
| vel_norm | `vel_norm` (44) | 速度大小 |
| ba_norm | `ba_norm` (45) | acc bias norm |
| bg_norm | `bg_norm` (46) | gyro bias norm |
| depth_mean/std | `depth_mean` (135), `depth_std` (138) | 特徵深度分布 |
| good_depth_ratio | 由 `good_depth_count` (133), `bad_depth_count` (134) 導出 = g/(g+b) | 深度可靠比例 |

> 全部 runtime-observable、部署可得；residual space 註記：VINS 視覺殘差為 normalized-coord（見記憶 residual-space-pixel-vs-normalized），與物體可信度的 pixel 量綱不同，NOUE 設計時需留意。

## 對齊工具 ✅
- `scripts/paper2_align_vins_quality_to_objects.py`（standalone, stdlib-only）。
- 功能：object-obs CSV（含 ts 秒）× reliability CSV → 每個 object-obs 取**最近時戳**的 reliability row，附上 v0 features（`--max-dt` gate，預設 0.2s；超 gate 標 `vins_match_ok=0` 且欄位留空，不編造）。

## join demo ✅
- `paper2_object_vins_quality_join_demo.csv`（repo root）。
- **機制 demo**：object-obs 為 mock（時戳取自 reliability CSV 範圍內；**非真實物體觀測**，真實的待 Workstream C/dynamic_v3 產出）。
- 結果：7 筆 mock object-obs，6 筆在 0.2s 內成功對齊真實 VINS quality（feature count、outlier ratio、ba_norm、`gyro_vins_so3_diff_deg`、good_depth_ratio 等），1 筆超範圍（999s）正確標 unmatched。
- 證明：物體觀測 ↔ VINS-quality 的最近時戳 conditioning 對齊**機制可行**。

## 明確 deferred（不在 G0，需後續另批准）
- estimator logging 補強：marginalization prior residual、IMU preintegration residual、parallax 統計、pose covariance proxy。
- NOUE 模型訓練。
