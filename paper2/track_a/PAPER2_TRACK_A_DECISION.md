# PAPER2 Track A — DECISION（誠實裁示）

> Track A 目標：檢查 Paper-2 能否升級成更強的 sequence-validity model（不只微調 TCSV-M）。
> 全部結論由**實跑**支撐（`PAPER2_SEQUENCE_MODEL_RESULTS.md`，no-torch 候選 + GRU/TCN/Transformer @ conda `gf` RTX 5090）。
> **壞結果照寫，不包裝。** 紅線全守：無 GT feature、無 frame-random、未碰 backend/object-factor/frontier/HD-map、不重錄 CARLA。
> 日期 2026-07-01。

---

## 勝利門檻對照（先講結論）

| 門檻 | 結果 |
|---|---|
| ≥2 真實資料集贏 cv_smoothing_gate | ❌ **未達**——只有 1 個真實資料集（KITTI）。KITTI 上 `seq_pool_hgbm` 強贏 cv（CI<0）；CARLA 是 synthetic 不算。 |
| ≥平手/小贏 learned selector baseline | ✅ **達成**——`seq_pool_hgbm` in-domain 贏 MLP/GRU/TCN/Transformer 全部 selector（CI>0 對方較差）。 |
| direct cross-dataset 不得大輸 | ⚠️ **部分**——real→synthetic(kitti→carla) `seq_pool_hgbm` 最佳；但 synthetic→real(carla→kitti) 仍輸 cv（+0.067）。 |
| 做不到就誠實停 IV/ITSC，不硬衝 | ✅ **採用**——見下方第 3、4 問。 |

---

## 四個最終回答

### 1. sequence model 是否真的比 TCSV-M 有價值？

**分兩層，答案相反：**

- **序列「特徵」(temporal pooling)：YES，真實小升級。** `seq_pool_hgbm`（mean/std/min/max/last/slope 池化 → HistGBM）在 KITTI / CARLA / mixed 三個 in-domain split **bootstrap CI<0 穩定贏 TCSV-M（~0.02–0.03 AURC）**，也贏 cv_gate，且可解釋。**建議把它升為新 final model**（取代 TCSV-M 的手工 14 摘要）。
- **序列「模型」(GRU/TCN/Transformer)：NO，不值得。** 三者在每個 in-domain/mixed split 都**輸給簡單池化 HistGBM**（CI>0），CARLA 上甚至比 TCSV-M 還差（薄 group 過擬合）。order-preserving flat MLP 也輸 order-agnostic 池化 → **順序結構無增益**。深度序列編碼器在此資料量是負投資。

> 一句話：**升級在特徵，不在模型。** 換 GRU/TCN/Transformer 是死路（已實證，非臆測）。

### 2. 需要補哪個資料集最划算？

**nuScenes（首選）。** GT velocity 官方直接給（label 最乾淨）、有 mini 4GB 可先驗證整條 pipeline、devkit 成熟、相機-3D 生態最豐富、reviewer 接受度高。次選 Argoverse 2，Waymo 因 TF 依賴+體積列最後。**這才是 binding constraint**：滿足「2 真實資料集贏 cv」只缺 nuScenes，與模型無關。（細節：`PAPER2_DATASET_EXPANSION_PLAN.md`。另：KITTI stereo redo 現已可行，image_03 已解壓。）

### 3. 是否值得把 Paper-2 往 RA-L / T-IV 衝？

**現狀不值得硬衝。** 理由：
- 序列模型給不出強升級（深度模型 = 負結果；池化只是小贏）。
- **只有 1 個真實資料集**，且 synthetic→real 直接遷移仍輸 cv。
- **唯一通往 RA-L 的路 = 補 nuScenes（第二真實資料集）+ KITTI stereo redo**，不是再加模型。
→ 若使用者願意投入 nuScenes（mini 先驗證、positive 再拉 full），則 RA-L 變可行；否則不衝。

### 4. 還是 Paper-2 應停在 IV/ITSC，把大貢獻交給 Track B？

**建議：Paper-2 定位 IV/ITSC，以 `seq_pool_hgbm` 為精煉後的 final model；大貢獻交給 Track B——除非決定投 nuScenes。**

- **若不補資料**：Paper-2 收斂在 IV/ITSC——誠實框架（selective validity + 池化時間一致性特徵 + cv 冷啟動 fallback），主張不靠複雜模型（已證深度模型無用），這反而是乾淨、可辯護的故事。大貢獻留給 Track B。
- **若補 nuScenes**：升級路徑明確（2 真實資料集 + stereo redo + 池化 final model + CI），可實衝 RA-L。

---

## 對 Paper-2 final model 的具體建議（誠實、可立即採用）

1. **final model：`seq_pool_hgbm`**（時間池化統計 → HistGBM），取代手工 14 摘要的 TCSV-M；保留 cv 冷啟動 fallback。
2. **明說**：深度序列編碼器經實測無增益（負結果照報，轉成「為何不需要序列網路」的洞見）。
3. **不衝 RA-L 的版本**：投 IV/ITSC，主打 framework + 池化特徵 + fallback policy。
4. **要衝 RA-L 的版本**：先補 nuScenes mini 驗證 → full + stereo redo + CI，再談。

## 產物（全部於 `paper2/track_a/`）
- `PAPER2_SEQUENCE_MODEL_FEASIBILITY.md`、`PAPER2_DATASET_EXPANSION_PLAN.md`、`PAPER2_SEQUENCE_MODEL_RESULTS.md`、本檔
- `scripts/paper2_sequence_validity_experiment.py`、`scripts/paper2_sequence_deep_models.py`
- `paper2_sequence_validity_metrics.csv` / `_bootstrap.csv`、`paper2_sequence_deep_metrics.csv` / `_bootstrap.csv`
