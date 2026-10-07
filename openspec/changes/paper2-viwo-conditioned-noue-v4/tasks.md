# Tasks — paper2-viwo-conditioned-noue-v4

> 分階段 gate。每個 gate STOP-and-report。跨 gate（大量錄製、NOUE 訓練、backend 改動）需使用者批准。
> 進度截至 2026-06-30 overnight push（見 `PAPER2_OVERNIGHT_MAX_PUSH_SUMMARY.md`）。

## Phase G0 — Data grounding ✅
- [x] G0.1 KITTI tracking image_2/image_3 補下載（背景中；watcher 等候解壓）
- [x] G0.2 CARLA recorder +type_id；dynamic_v3 probe；**24-run balanced dataset**（Town10HD+Town01 ×3 density ×4 spawn）
- [x] G0.3 probe 輸出檢查（gt 欄位完整含 type_id、depth/seg/flow）；seg-id≠actor-id（走 3D 幾何）
- [x] G0.4 raw object pipeline 產距離分 bin 誤差表（pos 1.93/2.12/7.79m median）
- [x] G0.5 VINS quality v0 schema + align tool + join demo
- [x] **G0 GATE PASS**（≥14 runs、matched 15811≫1000、各 bin 充足、趨勢可解釋）。註：未開 30 條（24 已足）；其餘 town 不穩。

## Phase G1 — Raw-estimator validation ✅
- [x] G1.1 raw geometry baseline（centroid-difference）誤差
- [x] G1.2 yaw injection 驗 e_lat≈r·sin(Δyaw)（per-detection lever）
- [x] G1.3 distance bins × density 誤差表（`PAPER2_RAW_OBJECT_BENCHMARK.md`）
- [x] G1.4 phase map v0（`PAPER2_PHASE_MAP_V0.md`）
- [x] **G1 GATE PASS** — 誤差單調可解釋。

## Phase G2 — NOUE training（object-side done; A2 blocked）
- [x] G2.1 dataset `paper2_object_dataset_v1.parquet`（15811，group-split）
- [x] G2.2 baselines：distance-only、geometry-gate
- [x] G2.3 NOUE-object（Σ_p NLL + invalid/obs/utility heads）；obs head AUROC 0.759
- [ ] G2.4 **A2 生死線 = BLOCKED**（需 VINS replay 產 reliability_features_vins.csv；不硬編）。object-side 對照 inconclusive（NOUE 勝 AUROC/risk-cov、輸 NLL）
- [x] G2.5 H1 residual refine 隔離 ablation（無改善，未進主模型）
- [x] G2.6 output policy（overconf 0.59→0.39）`PAPER2_OUTPUT_POLICY_RESULTS.md`
- [~] **G2 GATE**：MVP object-side 完成，但**核心 A2 未裁決**（blocked）→ 不可宣稱 method 成立；待 VINS replay。

## Phase G3 — Integration / utility gate（HELD）
- [x] G3.1 G3-lite 離線 utility gate 分析（`PAPER2_G3_LITE_UTILITY_GATE.md`）
- [ ] G3.2 object factor backend scaffold — **HELD**（A2 非 promising；不開 branch、不碰 backend）
- [ ] G3.3 real-data 驗證（KITTI tracking）— pending KITTI 解壓 + reader

## 跨階段
- [ ] Z1 投稿前核對 venue 分區
- [x] Z2 每 gate STOP-and-report；overnight summary 已出，等使用者 design checkpoint（首推授權 VINS replay 解 A2）
