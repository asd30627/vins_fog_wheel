# PAPER2 Track A — SEQUENCE MODEL FEASIBILITY

> 目的：判斷 Paper-2 能否從 tabular validator (TCSV-M) 升級成 sequence-level object-state validity model。
> 不微調 TCSV-M；探索更強方向。紅線：無 GT feature、無 frame-random、未碰 backend/object-factor/frontier/HD-map。
> 日期 2026-07-01。結論證據見 `PAPER2_SEQUENCE_MODEL_RESULTS.md`。

---

## 1. 現有資料盤點（Task 1）

| 資料集 | 路徑 | 狀態 |
|---|---|---|
| CARLA dynamic_v3 | `/mnt/sata4t/datasets/carla_fwvio/{Town01,Town10HD}__dynamic_v3__run*` | ✅ 可用，全感測器（stereo/depth/seg/flow/imu/gt）。**僅 2 town**，多 run（sparse/medium/dense × b1/r30/r60/r90） |
| KITTI tracking | `/mnt/sata4t/datasets/kitti/tracking/training/` | ✅ 可用，**image_02(左) + image_03(右) 皆已解壓**、calib/label_02/oxts 齊全 |
| **KITTI stereo redo** | 同上 image_03 | ✅ **現在可行**（image_03 不再損毀；先前 P0-5 blocker 已解除） |

**已抽好的 per-frame validity 表（可直接建序列）：**
- KITTI：`paper2/paper2_kitti_validity_dataset.csv` — 37,022 rows，**843 tracks，21 seqs**，track 中位長度 29，96% tracks≥5 frame，velocity_valid base rate **0.430**（平衡）。
- CARLA v5：`paper2/paper2_v5_object_validity_dataset.csv` — 15,811 rows，**359 tracks，2 town / 19 run**，track 中位長度 **7**（短！），僅 57% tracks≥5 frame，velocity_valid base rate **0.127**（極不平衡）。

**序列窗口可得量**（sliding，T=5）：KITTI ~33.7k、CARLA ~14.7k。**中等偏小**，且**泛化單位很薄**（KITTI 21 seq、CARLA 只有 2 town）。這是序列模型的根本限制。

---

## 2. 序列輸入設計（Task 2）

每個被標記 frame 取其 track 最後 **T=5** frame 的 RAW 可觀測狀態（edge-pad）。
per-frame 9 維共通特徵（雙資料集，無 GT）：
`range_m, depth_m, bbox_area, bearing_deg, det_conf, raw_speed, cv_residual, acceleration_score, track_age`
（range/depth/area 取 log1p；缺值以 train 中位數補）。
衍生表示：① 攤平 [T×F]（保留順序）② 池化統計 [6×F]（mean/std/min/max/last/slope）。
**未使用** GT velocity / GT trajectory / HD-map / occlusion-from-GT 作為 feature（occ/trunc 僅 KITTI 有，跨域共通 schema 排除）。

---

## 3. 序列模型候選（Task 3）— 全部實跑

| 候選 | 實作 | 需 torch | 結果（詳見 RESULTS.md）|
|---|---|---|---|
| TCSV-M（baseline）| HistGBM+mono on 14 摘要 | 否 | 現任 final，被池化超越 |
| temporal pooling MLP | MLP on 池化統計 | 否 | 贏 TCSV-M（KITTI 最佳之一）但跨域差 |
| **temporal pooling + HGBM** | HistGBM on 池化統計 | 否 | ✅ **整體最佳**：3 split CI<0 贏 TCSV-M+cv，且贏所有深度模型 |
| TCN | 2-layer Conv1d + GAP | 是(gf) | ❌ 輸 seq_pool_hgbm（CI>0）；CARLA 過擬合 |
| GRU | 1-layer GRU + head | 是(gf) | ❌ 輸 seq_pool_hgbm（CI>0）；CARLA 過擬合 |
| small Transformer | 1-layer encoder + posenc | 是(gf) | ❌ 輸 seq_pool_hgbm（CI>0）|

**justification for Transformer**：有跑（1-layer，dmodel=64），但在此資料量無優勢——未達「justified」門檻。

---

## 4. 可行性裁示

- **序列「特徵」可行且有真實小幅價值**：時間池化統計 → HistGBM 是對 TCSV-M 的 bootstrap-驗證升級。
- **序列「模型」（深度編碼器）不可行/不划算**：現有資料規模與薄 group 結構下贏不過簡單池化，且 synthetic 過擬合。順序結構未帶來增益。
- **瓶頸不在模型**：synthetic→real 直接遷移持續輸 cv_gate，且**只有 1 個真實資料集（KITTI）**——這是 Track A 升級到 RA-L/T-IV 的真正卡點，需靠資料集擴充（見 `PAPER2_DATASET_EXPANSION_PLAN.md`），不是換更花俏的模型能解。
