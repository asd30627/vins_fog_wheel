# PAPER2 G0 DATA-GROUNDING — SUMMARY

> Change: **paper2-noue-g0-data-grounding**（branch grade-fusion-v1）。2026-06-30。
> 低風險前置階段：未訓練 NOUE、未改 VINS estimator backend、未加 object factor、未重構主專案、未開大量錄製。

## 1. OpenSpec change
- Path：`openspec/changes/paper2-noue-g0-data-grounding/`（`proposal.md` / `design.md` / `tasks.md` / `specs/paper2-noue-g0-data-grounding/spec.md`）。
- `openspec validate paper2-noue-g0-data-grounding --strict` → **valid**；`openspec list` 已註冊。

## 2. KITTI tracking status（Workstream A）— ⏳ 下載進行中
| 五件套 | 狀態 |
|---|---|
| label_02 / calib / oxts | ✅ 完整（`unzip -t` OK；尚未解壓）|
| image_2（left）| ⏳ **下載中** 6.57 GB（wget -c PID 25596，前一 session 續傳，~5h+）|
| image_3（right）| ⏳ **下載中** 0.21 GB（wget -c PID 480480，本次起，ETA ~11h，鏈路極慢）|
- image_2 **完整？** 否（下載中，尚未 unzip 測）；image_3 **完整？** 否（下載中）。
- **解壓了嗎？** 尚未（待下載完成才能 unzip -t + 解壓 `training/image_02/`、`training/image_03/`）。
- file counts：待解壓。
- 決策：image_2 既有 wget -c 續傳中 → 不 mv/不重啟（避免打斷正在寫入的檔）。下載不阻塞其他 workstream。
- log：`download.log`（image_2）、`download_image3.log`（image_3）。詳見 `PAPER2_KITTI_TRACKING_ASSET_STATUS.md`。

## 3. CARLA dynamic_v3 probe status（Workstream B）— ✅ 成功（使用者授權啟動 server 後）
- **B1 ✅**：`collect_carla_v2.py` per-instance 加 `type_id`（GT-only，1 行；備份 `*.bak_20260630_021455` + diff；py_compile OK）。
- **B2 ✅**：`run_carla_dynamic_v3_probe.sh`。
- **CARLA server ✅**：docker `carla0916`（專案 recipe，headless port 3000）已啟動並就緒（0.9.16, Town10HD_Opt）。⚠ **仍在執行，佔 GPU；停止 = `docker stop carla0916`**。
- **B3 ✅**：probe rc=0 → `/mnt/sata4t/datasets/carla_fwvio/Town10HD__dynamic_v3_probe__run01`，240 frames（60+100+80），npc 15，640×480，cleanup 乾淨。
- **B4 ✅**：gt=`per_instance_velocity_pose_bbox`；aux 各 240 檔；per_instance 欄位齊全含 **type_id**（class 記錄成功）+ 位置 + bbox。
- **B5 ✅（發現）**：**seg-instance-id ≠ actor-id**（唯一重疊巧合）→ 關聯走 3D 幾何最近鄰，非 seg-id。詳見 `PAPER2_CARLA_DYNAMIC_V3_PROBE.md`。

## 4. Raw object probe status（Workstream C）— ✅ Q-A 首次量化
- script ✅：`scripts/paper2_raw_object_probe.py`。
- **distance-bin error table = 產出**（240 frames、338 偵測、122 匹配；body-frame bearing 匹配，首跑修了 world-frame 座標慣例 bug）：
  | bin | n | pos_err med | pos_err p95 | spd_err med | 
  |---|---|---|---|---|
  | 0-15m | 6 | 1.30m | 2.70m | 2.96 m/s |
  | 15-30m | 37 | 2.97m | 3.58m | 3.72 m/s |
  | 30m+ | 79 | 8.35m | 45.83m | 38.03 m/s |
- raw 位置誤差隨距離暴增；30m+ 速度變 garbage（depth-jitter）；yaw 1° 注入確認 `e_lat≈r·sin(Δψ)`（30m+ ~58m → ~1.0m）。
- **caveats**：單 run 小樣本、bearing 匹配可能灌大 30m+ p95、速度方向初步。**G0 首跑非 benchmark。** 詳見 `PAPER2_RAW_OBJECT_PROBE_RESULTS.md`。
- 附帶：ultralytics 在 env `gf` AutoUpdate 裝 `lap-0.5.13`（ByteTrack 依賴）。

## 5. VINS quality feature schema status（Workstream D）— ✅ 完成
- **使用哪些現成欄位**：timestamp, tracked_feature_count_raw/mgr, outlier_ratio_last, coverage_8x8, avg_track_length, solver_time_ms_last, failure_detected_last/reason, gyr_z_mean/std, gyro_vins_so3_diff_deg, vel_norm, ba_norm, bg_norm, depth_mean/std, good_depth_ratio（由 good/bad_depth_count 導出）。全為 `reliability_features_vins.csv` 既有欄位。
- 對齊工具 ✅：`scripts/paper2_align_vins_quality_to_objects.py`（最近時戳，stdlib-only）。
- **joined demo 是否產生？** 是 — `paper2_object_vins_quality_join_demo.csv`（機制 demo，mock object-obs；6/7 在 0.2s 內對齊真實 VINS quality）。詳見 `PAPER2_NOUE_FEATURE_SCHEMA_V0.md`。
- deferred（不在 G0）：estimator logging 補強（marg/IMU 殘差、parallax、cov proxy）、NOUE 訓練。

## 6. 風險 / blocked items
1. **KITTI 鏈路極慢**（~0.15–0.7 MB/s，多下載搶頻寬）→ image_2/image_3 完成數小時級，時間不確定；完成前無法 unzip/解壓（A4/A5 pending）。
2. **CARLA container `carla0916` 仍在跑**（佔 GPU）→ 不再需要時 `docker stop carla0916`。
3. raw object 誤差表為 **G0 首跑**：單 run 小樣本、bearing 匹配可能灌大 30m+ p95、速度方向初步。需多 run/density 才成 benchmark（gated）。
4. seg-instance-id ≠ actor-id（已實測）→ 關聯一律走 3D 幾何，已內建於 pipeline。

## 7. 下一步建議（不自行擴張到訓練 NOUE）
1. **Q-A 已量化**（pos err 1.3→3.0→8.4m median，遠距速度爆）→ 由使用者決定是否批准 **~30 條大量錄製（多 town/density）** 把首跑升級為正式 benchmark（probe-before-bulk gate；probe 已成功）。
2. KITTI image_2/image_3 下載完成後做 A4/A5（unzip + 解壓 + 完整性報告）。
3. 之後（需批准）才進 v4 的 G1（raw-estimator validation）→ G2（NOUE 訓練 + A2 生死線）。
4. estimator logging 補強（marg/IMU 殘差、parallax、cov proxy）仍 deferred，需另批准。

**STOP，等使用者做下一個 design checkpoint。CARLA server 仍開著（供你決定是否續錄/停）。**
