## Why

Paper-2 的完整設計（v0.4，source = `viwo_conditioned_noue_spec_v04.md`）。這是 Paper-2 / 國科會研究項目 3 的**總綱 OpenSpec change**——把全案（問題、貢獻、pipeline、模型、資料、評估、red lines、分階段）落成可管控的 spec。**執行採分階段 gate**：G0（data grounding）的細節執行在 sub-change `paper2-noue-g0-data-grounding`；本 change 是涵蓋 G0→G3 的 master design。

**一句話定位.** 在 GPS-denied 的 VINS-Fusion / optional wheel 定位退化條件下，動態物體的位置與速度估計會被 ego-pose uncertainty 污染。本研究提出 **NOUE（Neural Observability and Uncertainty Estimator）**：一個由 **VINS/VIWO localization-quality features 條件化**的學習式可觀測性與不確定性估計模組，判斷「每個動態物體的狀態此刻有多可信、可不可觀測、該不該輸出或回饋」，並建立 **localization-quality × dynamic-condition × distance 的 phase map**。

**為什麼這不是 incremental.** 既有 object-uncertainty 方法（Gaussian YOLO、MonoRUn、3D-MOT covariance learning）把不確定性 condition 在**感測證據**（影像/深度/偵測信心/遮擋/LiDAR 稀疏度）。本研究研究一個**互補且少被探討的 conditioning 維度**：VINS/VIWO **定位品質**如何影響動態物體狀態的可信度。這條窄縫是核心新穎性。

**兩根支柱（不押單一賭注）.**
- **Pillar 1 — Phase map / benchmark（measurement contribution）**：系統性建立「定位品質 × 動態密度 × 物體距離 × 運動形態」如何影響 object state reliability。即使 NOUE 的 A2 ablation 不顯著，這根仍可成文。
- **Pillar 2 — NOUE 方法（method contribution）**：學習 object state 的 uncertainty / observability / utility，尤其 condition on VINS/VIWO quality，讓 AI 成為主角而非 YOLO/SAM 後處理的規則式 gate。

**精準 claim（投稿用）.** *Existing object-uncertainty methods mainly condition uncertainty on sensing evidence (image, depth, detection confidence, occlusion, LiDAR sparsity). We study a complementary and under-explored conditioning dimension: how VINS/VIWO localization quality affects dynamic object state reliability in GPS-denied navigation.*

**Grounding（來自 CC Q-A/Q-B 調查，2026-06-30，provenance 見 `PAPER2_INVESTIGATION_QA_QF.md`）.** Q-B（conditioning 地基）= 綠燈：VINS quality features 多數現成（`reliability_logger.h` ~150 欄）。Q-A（感知地基）= 目前缺資料：唯一動態錄製只有 velocity GT、無 position/bbox/depth/seg；故 Q-A 從「已可量化」**降級為 Gate G0**，補資料後才量。

## What Changes

- **新增 capability `paper2-viwo-conditioned-noue-v4`**：Paper-2 的完整設計與分階段 gate（G0 data grounding → G1 raw-estimator validation → G2 NOUE training → G3 integration/utility gate）。
- **核心方法 NOUE（sidecar，不取代任何既有模組）**：輸入 = object 觀測特徵（bbox/mask/depth/flow/track/parallax/range/bearing-change）+ raw state（ego-comp 後 p_raw/v_raw）+ VINS reliability features；輸出 = position uncertainty `Σ_p`、velocity uncertainty `Σ_v`、observability score `q_obs`、utility score `u`、invalid-velocity 機率 `p_invalid_vel`。
- **Phase map / benchmark**：localization-quality 軸（yaw 注入 0.5/1/2°、position/scale drift、low-feature/high-outlier、gyro-vision disagreement、optional wheel slip）× dynamic/object 軸（density、distance bin 0-15/15-30/30m+、car-following、lateral crossing、occlusion、low-disparity、high ego-yaw-rate）。
- **Uncertainty-driven output policy（active behavior，加厚貢獻）**：full-state / high-covariance / position-only / invalid-velocity / conservative-warning 分級輸出。
- **H1（state residual refine）明確排除於主模型**，僅作隔離 ablation（避免變成 learned 3D object estimation 撞 scene-flow/3D-MOT，且避免搶 uncertainty head 的訓練信號）。
- **A2 生死線**：NOUE-full（含 VINS quality）必須在**定位退化 bins** 勝過 NOUE-without-VINS-quality；不成立則全案從 method paper 降級為 benchmark/measurement paper。
- **資料計畫**：CARLA dynamic_v3 為主（監督式 object-state GT），KITTI tracking 為真實資料備援，KAIST/VINS reliability 支撐 conditioning 分布。

## Capabilities

### New Capabilities
- `paper2-viwo-conditioned-noue-v4`：VINS/VIWO localization-quality-conditioned 的動態物體狀態可信度估計（NOUE）+ phase-map benchmark + uncertainty-driven output policy，採 G0→G3 分階段 gate，G0 嚴格 red lines（不訓練、不改 VINS backend、不加 object factor、不開大量錄製，皆 gated）。

### Modified Capabilities
<!-- None. 與 grade-conditioned-inertial-fusion（Paper-1，FOG 旋轉仲裁）正交，不更動其五錨點/三坑/rotation-only。本 change 是 Paper-2 獨立 capability。G0 細節執行在 sub-change paper2-noue-g0-data-grounding。 -->

## Impact

- **MVP 不改 VINS-Fusion backend**：NOUE 是 reliability sidecar；object factor / localization feedback 僅 G3 optional，且 disabled 時 baseline 須 bit-identical。
- **新增 standalone 產物**：object front-end、NOUE 訓練/評估、phase-map、output-policy 皆 standalone（不進 estimator 主流程）。
- **資料**：CARLA dynamic_v3 重錄（含 position/bbox/class/depth/seg GT）；KITTI tracking 備援；wheel 為 optional conditioning feature（claim = 提供獨立 ego-motion/scale 一致性訊號，**非** "wheel 改善 ATE"）。
- **Gate / red lines**：G0 不訓練 NOUE、不改 backend、不加 object factor、不開 ~30 條大量錄製；probe 成功後須使用者批准才放行下一步。所有結果附 provenance；不確定處寫「無法確認，需要 X」。
