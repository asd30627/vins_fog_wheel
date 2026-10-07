# PAPER2 Track A — DATASET EXPANSION PLAN

> 目的：評估補哪個資料集最划算，以滿足勝利門檻「**至少 2 個真實資料集上贏 cv_smoothing_gate**」。
> 現況：真實資料集只有 **KITTI tracking** 一個（CARLA 為 synthetic）。這是 Track A 衝 RA-L/T-IV 的binding constraint。
> 日期 2026-07-01。紅線：無 GT feature、無 frame-random、未碰 backend/object-factor/frontier/HD-map、不重錄 CARLA。

---

## 1. 每個 validity pipeline 需要的東西

要產生我們的 (feature, label) 表，目標資料集必須能提供：
1. **raw object estimate**（影像偵測 + 深度/3D → range/bearing/raw position/raw velocity；可重用現有 YOLO+depth 前端，env `gf`）
2. **GT object trajectory / velocity**（用來算 label，feature 不准用）
3. 可導出 **velocity_valid**（ego-independent vel_err ≤ 3 m/s）與 **position_valid**（pos_err ≤ 3 m）
4. **by-sequence / by-log cross-dataset split**（非 frame-random）

---

## 2. 磁碟現況

| 候選 | 磁碟上 | 可用性 |
|---|---|---|
| nuScenes | 只有 `mmdetection3d/{demo,tests}/data/nuscenes`（測試樁，極小）| ❌ 需下載 |
| Waymo Open | 只有 `mmdetection3d/tests/data/waymo`（測試樁）| ❌ 需下載 |
| Argoverse 2 | 無 | ❌ 需下載 |
| KITTI raw | `/home/ivlab3/datasets/kitti_raw` | ⚠️ 與 KITTI tracking 同 domain，**不算第二真實 domain** |

---

## 3. 三大候選 feasibility 與成本

| 維度 | **nuScenes** | Waymo Open | Argoverse 2 |
|---|---|---|---|
| GT 物體速度 | ✅ 官方直接提供 (vx,vy) | ✅ 提供 | ✅ 提供 |
| 3D tracking GT | ✅ 700/150/150 scenes, 23 cls | ✅ 大量 | ✅ Sensor + Motion Forecast |
| 相機 raw estimate 可行 | ✅ 6-cam 環視，camera-3D detector 多 | ✅ 5-cam | ✅ 7-cam ring |
| 官方 devkit | ✅ `nuscenes-devkit`（成熟、pip）| ⚠️ 需 TF / waymo-open-dataset | ⚠️ `av2` SDK |
| 原型用小切片 | ✅ **mini ~4GB**（10 scenes，可先驗證 pipeline）| ❌ 無官方 mini（單片 ~不一）| ⚠️ 較大 |
| 完整下載量 | ~300GB（trainval）/ mini 4GB | ~1TB+ | ~1TB+ |
| dt | 關鍵幀 2Hz（box）/ sweeps 更密 | 10Hz | ~10Hz |
| 與我方 pipeline 契合度 | **高**（單目 bbox+depth→range/bearing 流程可直接套）| 中（資料巨大、TF 依賴）| 中 |
| **成本/效益排名** | **① 最划算** | ③ | ② |

---

## 4. 建議

**首選 nuScenes**（理由）：
- GT velocity 官方直接給，label 推導最乾淨、爭議最小。
- 有 **mini (4GB)** 可先把整條 (feature→label→split) pipeline 驗證通，再決定是否拉 full trainval。
- devkit 成熟、相機-3D 生態最豐富，可重用現有前端（env `gf`）。
- nuScenes 是 driving-perception 標準第二資料集，reviewer 接受度高。

**最小可行路徑（cost-ranked）：**
1. **P0**：抓 nuScenes **mini**，跑前端產 raw object estimate，與 GT velocity 匹配 → 出 `paper2_nuscenes_validity_dataset.csv`（schema 對齊 KITTI 9 維 + label）。驗證 `seq_pool_hgbm` 是否在 nuScenes in-domain 也贏 cv_gate。
2. **P0**：**KITTI stereo redo**（image_03 已可用）→ 清掉單目深度混淆，重算 KITTI 全部數字（移除最大資料品質攻擊 R2）。
3. **P1**：若 mini 驗證 positive，拉 nuScenes full trainval（~300GB，磁碟尚餘 121GB → 需清空間或外接），跑完整 cross-dataset（KITTI↔nuScenes 真實↔真實遷移）。
4. **P2（備案）**：若 nuScenes 不順，退 Argoverse 2（GT velocity 亦佳）。Waymo 因 TF 依賴 + 體積，列最後。

**勝利門檻對照：** 只要 nuScenes in-domain `seq_pool_hgbm` 贏 cv_gate（KITTI 已贏），即達成「2 個真實資料集贏 cv」——這才是把 Paper-2 推向 RA-L 的關鍵，而非換模型。

---

## 5. 執行狀態（LIVE，2026-07-01 啟動）

### nuScenes — 下載中（**不需帳密**）
- **重大發現**：官方 CloudFront 公開 URL 全部回 HTTP 200，**免登入直接可下載**。
  `https://d36yt3mvayqw5m.cloudfront.net/public/v1.0/v1.0-trainval{meta,01..10}_blobs.tgz`
- 完整 v1.0-trainval = meta(0.4GB) + 10 blobs = **293.3 GB**，已驗證 11/11 可抓。
- aria2c 16 連線 × 3 並行下載到 `/mnt/sata4t/datasets/nuscenes/`。
  URL 清單：`paper2/track_a/nuscenes_urls.txt`；log：`paper2/track_a/nuscenes_download.log`。
- ingestion env：獨立 conda **`nusc`**（python3.9 + nuscenes-devkit 1.1.11 + pandas，與 `gf` 隔離，避免污染）。

### CARLA — 擴充 campaign 進行中（Town06 + Town07，2→4 towns）
- image `carlasim/carla:0.9.16-maps`（含 Town06/07），容器 `carla_dyn` port 3000（`--entrypoint bash` 覆蓋 image 的 `sleep` entrypoint）。
- Town06/Town07 探針皆 rc=0（dynamic_v3 recipe 在新 town 可用）。
- jobfile：`paper2/track_a/carla_expansion_town06_07.jobs`（各 12 runs：sparse/medium/dense × b1/r30/r60/r90，NPC 25/50/70，560 frames，spawn 0/30/60/90）。
- driver：`fwvio_ws/scripts/paper2_carla_dataset_driver_v2.sh`；log：`paper2/track_a/carla_expansion_campaign.log`。
- 輸出到 `/mnt/sata4t/datasets/carla_fwvio/Town0{6,7}__dynamic_v3__run*`。

## 6. 資料到位後的 ingestion 計畫（待執行）

**CARLA（先完成，~1h）：**
1. 對新 town runs 跑 `scripts/paper2_raw_object_benchmark.py` → per-det CSV → 併入 `paper2_raw_object_benchmark_all*.csv`。
2. 重建 4-town validity 表 → 重跑 Track A `seq_pool_hgbm`（驗證 town 多樣性是否改善 CARLA 過擬合 / cross-town 泛化）。

**nuScenes（~數小時）：**
1. 解壓 meta + blobs。
2. `nusc` env 讀 GT（3D box + velocity + ego pose）；`gf` env 跑偵測前端產 raw object estimate。
3. 匹配 → 導出 `paper2_nuscenes_validity_dataset.csv`（schema 對齊 KITTI 9 維 per-frame + velocity_valid/position_valid label）。
4. 跑 `seq_pool_hgbm` nuScenes in-domain vs cv_gate → **檢驗「2 個真實資料集贏 cv」勝利門檻**。
5. KITTI↔nuScenes 真實↔真實 cross-dataset。
