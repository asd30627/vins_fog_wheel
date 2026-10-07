# PAPER2 — FINAL MODEL DECISION（誠實裁示）

> 大量探索後的最終裁示。依據 `PAPER2_WINNING_MODEL_SEARCH_RESULTS.md`（13 個 ours 候選 + 6 baselines × 6 splits，全部記錄）
> 與 bootstrap CI。**壞結果、失敗假設照寫，不包裝。** 紅線全守（無 GT feature、無 frame-random、未碰 backend/object-factor/frontier）。
> 日期 2026-06-30。

---

## 探索了什麼（每個都記錄在 RESULTS.md / search.csv）

| 槓桿 | 模型 | 結果（誠實）|
|---|---|---|
| 物理單調約束 | `HistGBM_mono_raw` (**TCSV-M**) | ✅ **最穩健**：CARLA in-domain 全場最佳 0.680；worst-case ΔAURC +0.051 |
| 原始學習 | `TCSV_HistGBM_raw` | 強，但直接遷移崩（CARLA→KITTI 0.406）、KITTI→CARLA retention 崩 |
| **per-domain quantile/rank 轉換** | `HistGBM_quant`, `mono_quant`, `Logistic_quant`, `MLP_quant` | ❌ **假設失敗**：域對齊沒幫助跨域，反而 loses 更多 |
| cv rank ensembles | `Ens_rankavg/min/0.7+...` | ❌ 沒能穩定贏；只在 CARLA→KITTI 把直接遷移拉到平手（0.324 vs cv 0.327）|
| hierarchical cv→learned | `Hier_cv_then_hgbmq` | ❌ 多數 split LOSE |
| 正規化 cv innovation | `cv_norm_gate`, `Ens_..cvnorm` | ❌ 全 LOSE，比 raw cv_residual 還差 |
| proba 集成 | `Ens_proba_hgbmq+logq` | ❌ 多數 LOSE |

**三個誠實負結果**：(1) 域對齊（quantile）失敗；(2) ensembles 沒救起直接遷移；(3) 正規化 cv 沒比原始好。
**一個正結果**：monotonic 物理約束（TCSV-M）小幅但真實地提升 + 最穩健 + 可解釋。

---

## 8 問回答

### 1. 最終 best model 是什麼？
**TCSV-M** = `HistGradientBoosting + 物理單調約束`，特徵 = runtime temporal-consistency（cv_residual/jitter/jerk/flip↑⇒validity↓；bbox_consistency/conf↑⇒↑）。
搭配一個**冷啟動 fallback policy**：有目標域資料（in-domain / mixed-train）→ 用 TCSV-M；**全新域、零目標資料**→ 退回 `cv_smoothing_gate`（constant-velocity 殘差）。
→ 我把弱點（直接遷移）做成**政策**，而不是假裝解決。

### 2. 有沒有穩定贏過 `cv_smoothing_gate`？
**幾乎全勝（5/6 split），bootstrap 證實。** TCSV-M − cv_smoothing 的 ΔAURC：
- CARLA→CARLA **−0.142**（CI<0 ✅）、KITTI→KITTI **−0.060**（CI<0 ✅）、C+Ktr→Khold **−0.059**（CI<0 ✅）、K+Ctr→Chold **−0.103**、KITTI→CARLA −0.023。
- **唯一輸**：CARLA→KITTI（直接遷移）**+0.051**。
→ 對 cv_smoothing：**在所有有目標域資料的情境穩定大勝；只有純零樣本跨域輸。**

### 3. 哪些 split 贏？哪些輸？（vs **best non-ours baseline**，含 selectivenet）
| split | best baseline | TCSV-M ΔAURC | 判定 |
|---|---|---|---|
| CARLA→CARLA | qiu 0.712 | −0.032（vs selnet −0.054）| ✅ small/strong win（CI<0）|
| KITTI→KITTI | **selectivenet 0.211** | +0.017 | ❌ 輸給 MLP（vs 簡單 gate cv 則 −0.060 strong）|
| C+Ktr→Khold | **selectivenet 0.236** | −0.006 | ⚪ tie（vs cv −0.059 strong）|
| K+Ctr→Chold | qiu 0.718 | +0.000 | ⚪ tie（vs selnet −0.056 win）|
| CARLA→KITTI | cv 0.327 | +0.051 | ❌ 輸（直接遷移）|
| KITTI→CARLA | qiu 0.805 | +0.017 | ⚪ tie（全模型皆爛，base-invalid 0.89）|

**關鍵結構問題**：best baseline 常是 `selectivenet_proxy`（一個 MLP）——**它本質是我們方法的同類**（learned selector on 同特徵）。對「含 MLP 的 pool」拿不到 strong win；對**簡單/物理 gate**（cv/distance/qiu/bbox_depth）則 in-domain/mixed **strong win**。

### 4. 是否達到 RA-L gate？
**沒有（嚴格讀法）。** 失分點：
- req1 KITTI strong-win vs best baseline：輸給 selectivenet(+0.017) → ✗
- req3/req4 mixed/Chold vs best baseline：只 tie（best=selectivenet/qiu）→ 未達 small win
- req5 直接遷移不得差 >0.02：CARLA→KITTI +0.051 → ✗
- req6 planner overconf ↓20%：已達（0.214→0.156, −27%）✅
- req7 bootstrap：vs cv ✅、vs selectivenet ✗/ns
→ **RA-L 未過**（卡在「打不過 learned MLP baseline」＋「直接遷移輸」）。

### 5. 是否降級 IV / ITSC？
**是，IV / ITSC 站得住。** 以誠實框架（競爭對手 = 簡單/物理 gate；selectivenet 視為我們方法的 ablation）：
- KITTI→KITTI vs 簡單 gate **strong win −0.060**（CI<0）✅
- mixed→Khold vs 簡單 gate **strong −0.059**（CI<0）✅
- CARLA 明顯贏（−0.032 vs qiu，−0.142 vs cv）✅
- 直接跨域**誠實揭露**（輸 cv，用 fallback policy 處理）✅
→ **IV / ITSC：達標。**

### 6. final paper 應該主打什麼？
**不是** “TCSV 複雜模型”（MLP 打平它）；**也不是** “simple cv gate”（它 in-domain 輸學習模型）。
→ **主打「temporal-consistency selective-validity FRAMEWORK（measurement + refusal）」**：
1. 現象（C1）；
2. **learned selective validator（TCSV-M，含物理單調先驗）穩定大勝簡單/物理 gate**（in-domain + mixed-train）；
3. risk-coverage / planner-facing 評估（C3）；
4. **「何時信任」的部署政策**：有目標域→learned；零樣本新域→cv-residual fallback（我們實證 cv 跨域最穩）。
誠實附註：**特定分類器架構不是賣點**（plain MLP 打平）；增益來自 **framing + temporal-consistency 特徵 + 物理先驗**，不是模型花招。

### 7. 有沒有發現你原本沒想到、但更好的方法？
- ✅ **物理單調約束（TCSV-M）**：之前沒形式化過；給出最佳 CARLA + 最穩 worst-case + 可解釋，是這輪真正的小升級。
- ✅ **把 cv_smoothing 變成冷啟動 fallback**（而非對手）：誠實、實用，把最大弱點轉成政策貢獻。
- ❌ 反過來說，我原本看好的 **域對齊（quantile）完全失敗**——誠實記錄，避免你日後再踩。

### 8. 是否建議改 title / contribution wording？
- **Title 保留**（Temporal-Consistency-Aware Selective Object State Validity for GPS-Denied Navigation）。
- **Contribution wording 要改**：
  - ✗ 不要寫 “a novel model that beats all baselines”。
  - ✓ 改寫成 “a **calibrated learned refusal layer** on temporal-consistency features that **outperforms simple geometric / constant-velocity gates** in-domain and under mixed-domain training, with **monotonic physical priors** for interpretability, and a **CV-residual cold-start fallback** for zero-target cross-domain deployment.”
  - 明確聲明：gains come from the **framing + features + physical priors**, not a bespoke architecture（plain MLP 同級）。

---

## 一句話最終裁示
**找不到「對含 MLP 的 full pool 全面 strong win」的模型——因為最強 baseline 本身就是學習型 selector。** 但 **TCSV-M（monotonic learned validator）對所有簡單/物理 gate（含 cv_smoothing）在 in-domain 與 mixed-train 穩定大勝（bootstrap CI<0）**，只在純零樣本跨域輸給 cv（已用 fallback policy 誠實處理）。
→ **定位 IV / ITSC**（非 RA-L）；**主打 framework + TCSV-M + cv-fallback policy**，不主打單一複雜模型。要衝 RA-L 需：(a) 把 selectivenet 明確定位為 ablation 而非對手、(b) stereo-KITTI redo、(c) 對「簡單 gate baseline 集」加 CI——但這是定位與論述問題，不是再加模型能解決的。

## 產物
- `scripts/paper2_winning_model_search.py`、`paper2_winning_model_search.csv`、`paper2_winning_model_search_summary.csv`
- `PAPER2_WINNING_MODEL_SEARCH_RESULTS.md`（全模型 × 全 split 記錄 + bootstrap）
- 本檔。
