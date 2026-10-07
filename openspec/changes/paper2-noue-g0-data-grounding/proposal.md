## Why

Paper-2（VIWO-conditioned NOUE：在 GPS-denied、VINS-Fusion(+optional wheel) 定位不完美時，用學習式模組估計「動態物體位置/速度估計此刻有多可信」，核心是把不確定性 **conditioned on VINS 定位品質**）的可行性，壓在兩個地基上。地基調查 Q-A~Q-F 已完成（見 repo root `PAPER2_INVESTIGATION_QA_QF.md`，2026-06-30），結論：

- **Q-B（conditioning 地基）= 穩**：VINS 品質 features 多數現成可取（`reliability_logger.h` ~150 欄，部署即時可得）。
- **Q-A（感知地基）= 目前無法量化**，但**非結果差，而是資料+管線缺席**：`/mnt/sata4t/datasets/carla_fwvio/` 沒有「動態物體 + 物體位置 GT」同時存在的錄製（dynamic_dense 只有速度；clean 有位置但 `n_npc=0` 只剩 ego；唯一兼具者 `dynamic_v2` 目錄已刪）。KITTI tracking 立體影像未到位（left zip 截斷、right 缺）。

本 change 的唯一目標是**把 Q-A 的地基補起來、並用最小成本驗證 Q-A 是否可量化**——這是 G0（data-grounding）前置階段，**不是** NOUE 方法/訓練本身。本 change 刻意低風險：不訓練模型、不改 VINS-Fusion estimator backend、不加 object factor、不重構主專案。OpenSpec 在此僅作紀錄與管控。

## What Changes

四條獨立工作流（彼此不阻塞）：

- **A — KITTI tracking 立體影像補齊**：用既有可靠來源（avg-kitti S3 bucket，與現存 `kitti_dl.sh` 同源）可續傳補齊 `data_tracking_image_2.zip`（截斷）與 `data_tracking_image_3.zip`（缺），解壓並出完整性報告。**本 change 不寫 KITTI tracking 的 VINS reader**（留待後續）。
- **B — CARLA dynamic_v3 補錄能力**：對 `collect_carla_v2.py` 做**僅限 GT 欄位**的小改（per-instance 加 `type_id`），不動主錄製流程；新增一個 dynamic_v3 **probe** 腳本（小規模：40~80 frames、npc 15、不 `--skip-aux`）。**大量錄製（~30 條）需 probe 成功並回報後由使用者批准**，不在本 change 自動執行。
- **C — 最小 raw object pipeline（standalone）**：用現成零件（`gf` env：YOLOv8m + OpenCV SGBM/KLT + ultralytics 內建 ByteTrack）組一支 **standalone** script，量出 Q-A 的距離分 bin 物體位置/速度誤差 + yaw 注入 probe。**不訓練、不碰 estimator、不加 factor。** probe 資料尚未產生時，script 仍可寫成可接受資料路徑，並誠實回報 blocked，不編造數字。
- **D — VINS quality features（先用現成）**：建立 NOUE conditioning 的 **v0 feature schema**（對齊現有 `reliability_features_vins.csv` ~150 欄），寫一支 standalone 的物體-觀測↔VINS-quality 最近時戳對齊工具，輸出 join demo。**本 change 不補 estimator logging**（marg/IMU 殘差、parallax、cov proxy 皆留待後續，需另行批准）。

## Capabilities

### New Capabilities
- `paper2-noue-g0-data-grounding`：Paper-2 NOUE 的資料地基與最小量化能力——KITTI tracking 立體資產補齊、CARLA dynamic_v3（含物體位置/bbox/class GT）補錄能力、最小 raw object 估計管線（standalone）、以及先用現成 VINS quality features 的 conditioning schema；全程低風險（不訓練、不改 estimator backend、不加 object factor），且大量錄製採 probe-before-bulk gate。

### Modified Capabilities
<!-- None. 本 change 不更動 grade-conditioned-inertial-fusion 的任何既有 requirement（五錨點、三坑、rotation-only 不受影響）。Paper-2 NOUE 是獨立 capability。 -->

## Impact

- **無 VINS estimator backend 改動**：Workstream D 只消費既有 `reliability_features_vins.csv`；不加欄位、不加 factor、不動 backend。
- **CARLA recorder**：只在 `/home/ivlab3/fwvio_ws/scripts/collect_carla_v2.py` 的 per-instance GT dict 加 `type_id`（GT 欄位，與主錄製流程正交）。`fwvio_ws` 非 git repo → 以備份檔 + unified diff 記錄變更。
- **新增 standalone 產物**（皆不進主流程）：`scripts/paper2_raw_object_probe.py`、`scripts/paper2_align_vins_quality_to_objects.py`、`run_carla_dynamic_v3_probe.sh`，及 repo root 報告 `PAPER2_KITTI_TRACKING_ASSET_STATUS.md`、`PAPER2_CARLA_DYNAMIC_V3_PROBE.md`、`PAPER2_RAW_OBJECT_PROBE_RESULTS.md`（或 `_BLOCKED.md`）、`PAPER2_NOUE_FEATURE_SCHEMA_V0.md`、`PAPER2_G0_DATA_GROUNDING_SUMMARY.md`。
- **Gate**：大量 CARLA 錄製（~30 條）與任何 estimator logging 補強，皆 STOP-and-report、待使用者批准；本 change 不自決放行。
- **Provenance**：所有結果附路徑、commit、指令、實際數字；不確定處寫「無法確認，需要 X」。
