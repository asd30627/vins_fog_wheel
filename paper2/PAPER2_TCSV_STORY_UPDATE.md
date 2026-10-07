# PAPER2 — TCSV STORY UPDATE（誠實裁示）

> 把 selective validity model 形式化為 **TCSV (Temporal-Consistency Selective Validator)** 後的實測結論。
> **壞結果照寫、不包裝。** 依據：`PAPER2_TCSV_RESULTS.md`（+ metrics/riskcov/window/importance CSV）。
> 主題不變：**Temporal-Consistency-Aware Selective Object State Validity for GPS-Denied Navigation**。日期 2026-06-30。

---

## TL;DR

- **方法感升級成立，但來源不是特徵花招，而是把問題重構成 selective-prediction + risk-coverage 目標。**
- **新的物理化 temporal residual 對準度幾乎沒幫助**（KITTI 微升、CARLA 微降）——誠實標註。
- **temporal-consistency 仍是主訊號**（TEMP 組 ≫ GEO），但主要由 `raw_speed` 扛；新 residual 只有 KITTI 的 `cv_residual` 真正有料。
- **selective-risk（AURC / overconf@retention）是 TCSV 真正贏 baseline 的地方**，尤其 KITTI。
- 連帶修正前作一個 CARLA grouping 問題，CARLA in-domain AUROC 由報的 0.873 → **0.800**（更可信，仍贏 distance）。
- **C1/C2/C3 維持，不發散。**

---

## 實測重點（全部來自 PAPER2_TCSV_RESULTS.md）

### A. selective-risk：TCSV 確實適合 refusal（這是賣點）
| scenario | model | AUROC | AURC↓ | overconf@ret.9 |
|---|---|---|---|---|
| KITTI→KITTI | distance_gate | 0.686 | 0.457 | 0.430 |
| KITTI→KITTI | **TCSV-HistGBM** | **0.923** | **0.210** | **0.250** |
| CARLA→CARLA | distance_gate | 0.755 | 0.773 | 0.815 |
| CARLA→CARLA | **TCSV-HistGBM** | **0.800** | **0.703** | **0.754** |
- KITTI **大贏**（AURC 砍半、保 90% valid 時錯誤速度 0.43→0.25）；CARLA **小贏**（base invalid 高、velocity 本質難）。
- CARLA+KITtrain→held-out-KITTI 也強（AURC 0.213, overconf@ret.9 0.269）；CARLA→KITTI 直接遷移仍弱（AURC 0.406 vs distance 0.456，只小幅好）。

### B. 新 residual vs 舊 OLD10（§2）— 中性，誠實
| dataset | OLD10 AUROC | TCSV14 AUROC | 判讀 |
|---|---|---|---|
| CARLA | 0.829 | 0.800 | 新特徵**略降** |
| KITTI | 0.919 | 0.923 | 新特徵**微升** |
→ **物理化 residual 不是增益來源。** 不得宣稱「新特徵贏舊特徵」。

### C. 特徵重要度（§3）— temporal 仍主導，但靠 raw_speed
- CARLA 組總和：TEMP_base **0.247** ≫ GEO 0.044 ≈ TEMP_resid 0.032。
- KITTI 組總和：TEMP_base 0.157 > TEMP_resid 0.093 > GEO 0.060。
- 單一最強：`raw_speed`（CARLA 0.193 / KITTI 0.140）。新 residual 唯一亮點 = KITTI `cv_residual`（rank 2, 0.061）。

### D. window ablation（§4）— 視窗不是槓桿
- CARLA W=1 (0.813) ≈ W=7 (0.824)；KITTI W=1 (0.917) → W=5/7 (0.923)。
- **W≈5 略優但差異極小**；不值得把「視窗長度」當賣點。

### E. honest corrections（我順手抓到的前作問題）
- 前作 CARLA temporal 以 `(run, track_id)` 分組，但 run 名跨 town 重複（Town01/dense_b1、Town10HD/dense_b1）→ **跨 town 混軌**。
- 改 `(town, run, track_id)` 後 CARLA in-domain HistGBM AUROC **0.873 → 0.800**（仍贏 distance 0.755）。KITTI 不受影響。
- → 之前 `PAPER2_SELECTIVE_VALIDITY_RESULTS.md` 的 CARLA +0.117 應修正為約 **+0.045**；KITTI 的強結論不變。

---

## 回答你的 5 個問題

**1. TCSV 是否比目前 10-feature HistGBM 更有方法感？**
**有，但方法感來自「問題重構」不是「特徵」。** 把它寫成 selective-prediction（learning-to-refuse）+ risk-coverage / AURC / overconf@retention 目標，是審稿人能認的方法層；外加可解釋 TCSV-rule、neural 對照、permutation importance、window ablation 的完整方法骨架。**但若只看「換了一堆新特徵讓準度變高」——沒有，那條路是中性/負的。**

**2. 新 temporal residual 是否真的提升？**
**整體沒有（誠實負/中性）。** CARLA 略降（0.829→0.800）、KITTI 微升（0.919→0.923）。唯一站得住的新特徵是 **KITTI 的 `cv_residual`**（importance rank 2）。其餘新 residual 大多被 `raw_speed` 涵蓋。寫稿要照實說。

**3. temporal window 多長最合理？**
**W≈5（差異極小）。** W=1 與 W=7 幾乎同分，視窗聚合不是強槓桿。可用 W=5 當預設，但**不要把視窗長度當貢獻**。

**4. SHAP / importance 是否支持 temporal-consistency 是主訊號？**
**支持「TEMP 組 ≫ GEO」這個層級的主張**（CARLA TEMP 0.247 vs GEO 0.044；KITTI TEMP 0.157 vs GEO 0.060）。**但要誠實限定**：主導者是 `raw_speed`（一個簡單的時序量），不是花俏的物理 residual。故事應講「raw 估計的時序量（速度量級/自洽性）比幾何/距離更具預測力」，而非「我設計的殘差特別強」。（用 permutation importance；未裝 shap，可日後補 SHAP 圖更直觀。）

**5. Paper-2 是否仍維持 C1/C2/C3，不再發散？**
**是。** C1 現象不變；C2 = TCSV（selective-prediction 形式化 + temporal-consistency 主訊號，數字依 grouping 修正）；C3 = risk-coverage / overconf@retention 的 decision-level 評估。**沒有新增方向、沒有碰 backend、沒有 frontier。**

---

## 我的建議（不急著寫稿，交你決定）

1. **把賣點定錨在 selective-prediction 框架**（C2+C3 合流：TCSV 是「learned selective validator」，用 risk-coverage 證明適合 refusal）。這比「新特徵」穩得多，也真的贏 baseline。
2. **新 residual 誠實降級為「formalization / interpretability」**：它們讓模型可解釋、physically-grounded，但不宣稱準度增益（除 KITTI cv_residual）。
3. **更新 `PAPER2_SELECTIVE_VALIDITY_RESULTS.md` 的 CARLA 數字**（grouping 修正，+0.117→+0.045），避免審稿被抓。
4. （可選）補 SHAP 圖把第 4 點視覺化；補 stereo-KITTI 看 cv_residual 是否更強（monocular depth 可能壓抑 bbox_depth_consistency）。

---

## 紅線（維持）
- 不寫正式初稿、不開 frontier/trajectory planning 主坑、不碰 VINS backend、不加 object factor。
- 不新增超出 TCSV 的大模型花樣（已守：無 transformer/attention）。
- 不把中性/負結果（新 residual、window）硬包裝成增益。

**STOP — TCSV 形式化 + 實測完成。方法感升級成立（靠 selective-risk 框架），新特徵中性、window 弱、temporal 仍主導但靠 raw_speed，並修正 CARLA grouping。C1/C2/C3 維持。等你裁示下一步。**
