# Design — paper2-noue-g0-data-grounding

> G0 data-grounding 前置階段。低風險、gated。本檔記錄設計決策與邊界，不展開方法/訓練細節。

## 範圍邊界（hard constraints）

| 允許 | 禁止 |
|---|---|
| 建本 OpenSpec change（紀錄/管控） | 訓練 NOUE / 寫方法模型 code |
| standalone scripts / reports | 改 VINS-Fusion estimator backend |
| 補齊 KITTI tracking 下載 | 加 object factor |
| 小改 CARLA recorder（僅 GT 欄位） | 重構主專案 |
| 跑小型 CARLA probe | 開 ~30 條完整大錄製（需 probe 成功+使用者批准） |
| 組最小 raw object pipeline（standalone） | 補 estimator logging（marg/IMU 殘差、parallax、cov proxy） |

## 各 Workstream 設計

### A. KITTI tracking 立體影像補齊
- **來源**：avg-kitti S3（`https://s3.eu-central-1.amazonaws.com/avg-kitti/data_tracking_image_{2,3}.zip`），與既有 `kaist_grade_scripts/kitti_dl.sh` 同 bucket、官方 KITTI 鏡像。**不自猜 URL。**
- **決策（已觀測到的事實驅動）**：`data_tracking_image_2.zip` 已有一個前一 session 的 `wget -c`（PID 25596）持續續傳中（檔案 5.7G→6.3G 成長）→ **不 mv、不重啟**（mv 會打斷正在跑的 wget），讓既有可續傳下載完成即可。`image_3` 無下載中 → 新起背景 `wget -c`。
- **完整性判準**：`unzip -t` 通過 + `unzip -l` 可列檔 + 解壓出 `training/image_02/`、`training/image_03/`。
- **不做**：tracking 的 VINS reader（後續 change）。

### B. CARLA dynamic_v3 補錄能力
- **recorder 改動最小化**：per-instance dict 已有 `speed/vx/vy/vz/x/y/z/yaw/ext`；只加 `type_id=a.type_id`（class）。其餘不動。`fwvio_ws` 非 git repo → 備份 + diff。
- **probe-before-bulk**：先跑一條 dynamic_v3 probe（40~80 frames、npc 15、含 aux：depth/seg/flow），驗證 GT 欄位完整 + aux 存在 + seg-instance-id 是否可對上 actor id，再回報。**大量錄製不在本 change。**
- **CARLA server 不可用時**：不自行啟動（避免破壞現場），STOP 回報 server 狀態 + 需使用者做什麼。

### C. 最小 raw object pipeline（standalone）
- **零件**：YOLOv8m（`kaist_grade_scripts/yolov8m.pt`）偵測 movable COCO 類 → bbox 內 stereo depth（OpenCV SGBM）robust centroid → 反投影 camera/body frame 3D → ultralytics `model.track()` 跨 frame association → ego-motion 補償 → raw velocity = compensated centroid diff / dt。
- **誤差**：對 CARLA GT `x,y,z,vx,vy,vz` 算位置/速度大小/速度方向誤差，分 bin 0-15/15-30/30m+。yaw 注入 probe：注 1° ego-yaw 看遠距 lateral error 是否 ≈ `r·sin(1°)`。
- **依賴 dynamic_v3 probe 的位置 GT**：probe 未成功則 script 仍可接受資料路徑，但輸出 BLOCKED 報告（不編數字）。

### D. VINS quality features（先用現成）
- **v0 schema**：對齊 `reliability_features_vins.csv`（實檔 156 欄）的現成欄位，**不補 estimator logging**。
- **對齊工具**：最近時戳 join（object-obs ts ↔ reliability-row ts），standalone。
- **join demo**：以現有 reliability CSV 展示對齊機制；真實 object-obs 待 Workstream C/probe 產出。

## 風險 / 待批准 gate
1. CARLA server 目前狀態未知/可能未開 → Workstream B/C 可能 blocked（誠實回報，不偽造）。
2. KITTI 鏈路慢（~0.42MB/s，多下載搶頻寬）→ image_2/image_3 完成時間不確定，不阻塞其他 workstream。
3. seg-instance-id ↔ actor-id 映射是否成立，需 probe 實測（`build_labels.py:117` 標 non-trivial）。
4. 大量錄製（~30 條）與 estimator logging 補強 = 後續 change，需使用者批准。
