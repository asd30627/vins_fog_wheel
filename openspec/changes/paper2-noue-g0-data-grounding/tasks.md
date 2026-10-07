# Tasks — paper2-noue-g0-data-grounding

> 每個 gate STOP-and-report（status + 數據 + provenance）。大量錄製 / estimator logging 補強需使用者批准。

## Workstream A — KITTI tracking 立體影像補齊
- [x] A1. 確認下載來源（既有 `kitti_dl.sh` 同源 avg-kitti S3；不自猜 URL）
- [x] A2. image_2：偵測到既有 `wget -c`（PID 25596）續傳中 → 不打斷，讓其完成（不 mv 正在被寫入的檔）
- [x] A3. image_3：新起背景 `wget -c`（記 PID + log 路徑）
- [ ] A4. （下載完成後）`unzip -t` + `unzip -l` 完整性測試
- [ ] A5. （完成後）解壓出 `training/image_02/`、`training/image_03/`，列檔數
- [x] A6. 出 `PAPER2_KITTI_TRACKING_ASSET_STATUS.md`（含進行中狀態快照）
- 不做：KITTI tracking VINS reader（後續 change）

## Workstream B — CARLA dynamic_v3 補錄能力
- [x] B1. `collect_carla_v2.py` per-instance dict 加 `type_id=a.type_id`（備份 + diff）
- [x] B2. 新增 `run_carla_dynamic_v3_probe.sh`（Town10HD、dynamic_v3_probe、run01、frames 80、npc 15、不 skip-aux）
- [x] B3. 跑 probe — 使用者授權啟動 CARLA server（docker carla0916）→ probe rc=0，240 frames
- [x] B4. probe 輸出檢查：gt=per_instance_velocity_pose_bbox、aux 各 240、per_instance 含 type_id+位置+bbox
- [x] B5. seg instance id ↔ actor id：**≠（非 seg-id，走 3D 幾何最近鄰）**
- [x] B6. 出 `PAPER2_CARLA_DYNAMIC_V3_PROBE.md`（probe 成功版）
- 不做：~30 條大量錄製（probe 已成功 → 等使用者批准放行）

## Workstream C — 最小 raw object pipeline（standalone）
- [x] C1. 寫 `scripts/paper2_raw_object_probe.py`（YOLOv8m + SGBM + ByteTrack + ego-comp + 距離 bin 誤差 + yaw 注入）
- [x] C2. probe 資料 → distance-bin error table（pos 1.30/2.97/8.35m med）→ `PAPER2_RAW_OBJECT_PROBE_RESULTS.md` + `paper2_raw_object_probe_results.csv`
- [x] C3. smoke-run（dynamic_dense）驗證管線可執行（已先做；BLOCKED md 已被 RESULTS 取代）
- 不做：訓練、NOUE、estimator 改動、object factor

## Workstream D — VINS quality features（先用現成）
- [x] D1. 整理現有 `reliability_features_vins.csv` / `reliability_dataset.tsv` 欄位
- [x] D2. 出 `PAPER2_NOUE_FEATURE_SCHEMA_V0.md`（v0 feature schema，對齊實際欄位）
- [x] D3. 寫 `scripts/paper2_align_vins_quality_to_objects.py`（最近時戳對齊）
- [x] D4. 產 `paper2_object_vins_quality_join_demo.csv`（對齊機制 demo）
- 不做：estimator logging 補強（marg/IMU 殘差、parallax、cov proxy）、訓練 NOUE

## 彙整
- [x] Z1. 出 `PAPER2_G0_DATA_GROUNDING_SUMMARY.md`
- [ ] Z2. STOP，等使用者做下一個 design checkpoint
