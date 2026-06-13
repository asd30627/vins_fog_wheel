# 設計短文 — 逐特徵可靠度計算法(T2,三案擇一)

**推薦預設:案 B(連續權重),最終依賴度 gated on Phase B `b1_se2_vs_b0.csv`。** 理由見末段。

## 共同輸入
每特徵每 keyframe 的運動參考一致性 d²(motion-reference-consistency),+ 選配 learned head 外觀純量 s∈[0,1]。

## 三案比較
| 案 | 機制 | 優點 | 缺點 | 工程量 |
|---|---|---|---|---|
| **A 硬門檻** | d²>τ_dyn → 剔除該特徵 | 最簡單、可解釋、與 DynaVINS 剔除類比 | 二元、邊界抖動、停車誤殺風險、丟資訊 | 最低(沿用 outlier 剔除路徑) |
| **B 連續權重**(推薦) | reliability = exp(−d²/2κ),映射到 visual_alpha(逐特徵)| 平滑、可融 learned s、資訊不全丟、接既有 √alpha hook | κ 需調、與 cov 有重疊風險 | 低(重用 visual_alpha hook) |
| **C 因子圖潛在可靠度狀態**(D7) | 每(模糊)特徵一個潛在 reliability 狀態進 Ceres 聯合最佳化 | 理論最強、可學習、與 robust-est 文獻接軌 | 最重、狀態爆量需選擇性、收斂/可觀測性風險、與本篇「規則式」定位衝突 | 高(估計器結構改動) |

## 推薦理由
- 案 B 平衡 rigor 與工程:連續權重保留資訊、可與 learned head s 相乘融合(s·exp(−d²/2κ))、直接走已 code-freeze 的逐特徵 √alpha hook(T5),不動估計器結構。
- 案 C 列 future(explore D7 已標 future change);本篇定位為「規則式幾何」,案 C 的潛在狀態屬學習式延伸,放第二章。
- 案 A 作消融下界(等價 κ→0 的硬化),不作主法。

## Gated 參數(待 Phase B)
- κ(權重陡峭度)與 learned 融合比:**最終值待 `b1_se2_vs_b0.csv`**。若 wheel SE(2) 在動態場景已大幅改善(ratio≪0.9)→ 幾何訊號可信 → κ 偏陡、learned 權重低;若改善有限 → 放寬 κ、提高 learned head 比重。
- τ_dyn(案 A/消融用):沿 integrity `dynamic_maha_min=16`(χ² 4σ)為起點。
