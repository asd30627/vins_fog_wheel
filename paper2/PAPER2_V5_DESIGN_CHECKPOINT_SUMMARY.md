# PAPER2 v5 — DESIGN CHECKPOINT SUMMARY (2026-06-30)

> Observability-Aware Dynamic Object State Validity for GPS-Denied Navigation。
> 期刊收斂判斷，**全程誠實、不包裝、不過度 claim**。紅線守住（未碰 backend / factor / G3 / 未重錄 / 未刪 v4）。
> 證據檔：robustness、OVI ablation、refusal trade-off、4 圖、文獻定位、evidence map、outline（清單見末）。

---

## Q1. v5 最終可主張的 claim 是什麼？
**可主張（有實證 + robust）：**
> 在 GPS-denied 常見道路幾何下，動態物體的**速度（有時連 full state）常常 weakly observable / unobservable**——這一現象**對 validity 閾值穩健**（27/27 threshold combos）。因此 **position 與 velocity validity 必須分開處理**；一個 **observability-aware validity layer**（輸出 full-state / position-only / invalid-velocity / unobservable / conservative-warning）在 **decision-level** 上能大幅降低 overconfident wrong-velocity（vs 永遠估）。我們提供 road-regime **validity phase map**、**multi-class refusal policy**、**decision-level evaluation**。

**不可主張（誠實刪除）：** first observability gating（Qiu 2018 已做）；OVI 勝 distance（實測 wash）；VINS-quality conditioning 有用（v4 A2 失敗）；object-consistency ego diagnostic 為正（C4 null）；conformal/uncertainty 為主創新。

---

## Q2. C1 / C2 / C3 哪個最強？（誠實排序）
1. **C1（validity 現象 + robust regime map）= 最強、最乾淨。** velocity_valid 隨距離崩 0.38→0.16→0.06（27/27 閾值穩健），velocity«position，position_only 是真 regime。這是論文脊椎，reviewer-proof。
2. **C3（refusal / validity LAYER）= 強，但強在「框架」。** 任何 observability-aware refusal 把 overconfident-wrong-velocity 從 no-policy 0.84 砍到 ~0.58-0.66 並保留速度；multi-class（position_only ~38%）有意義。**但 scorer 層面 OVI vs distance gate 是 wash（trade-off 曲線有 crossover，OVI 只 1/3 retention 點勝）。**
3. **C2（OVI 幾何 index）= 最弱。** 幾何項冗餘於 distance（overall AUROC Δ僅 **+0.008**；leave-one-out 每項 ≤0.003；只 15-30m 勝 +0.148，0-15m/30m+ 反輸）。**降為「可解釋輔助、增益 modest 且僅 mid-range」，不當主貢獻。**
4. C4（ego diagnostic）= **null**（rho≈0），誠實當負結果，不進主貢獻。

---

## Q3. 哪些 claim 必須收斂？
- 主貢獻收斂為 **C1（phenomenon + regime map）+ C3（validity-layer framework + decision-level eval）**。
- **OVI 降級**：不要說「我們的 index 比 distance 好」；說「一個可解釋幾何 index，增益 modest 且集中 mid-range；甚至簡單 distance/geometry gate 已實現大部分效益」（這本身是有用的誠實發現）。
- **刪 / 移到 limitations**：VINS-quality conditioning（v4 A2 負）、ego diagnostic（C4 null）。
- 用 "to our knowledge / we focus on / unlike methods that…"，**不用 "first"**。

---

## Q4. 和 Qiu 2018 的差異是否足夠？
**足夠成為 incremental 貢獻，但必須正面、明確處理，且 honestly 屬「延伸」非「顛覆」。**
- Qiu et al. IROS 2018：monocular VI、**單物體 scalar observability threshold**、**binary**（接受 / 只接受 up-to-scale）、4 種退化、評估 = tracking accuracy。
- 我們：(a) **road-geometry regime/phase map**（distance×density×bearing-change×depth），非單一 scalar；(b) **position/velocity validity 分離 + 5-way refusal**，非 binary；(c) **decision-level evaluation**（overconfident-wrong-velocity、false-refusal、planner-usable），非 tracking accuracy；(d) stereo+IMU road 場景的 deployable validity layer。
- **誠實**：差異真實但**漸進**。要讓差異「夠投稿」，最有力的補強 = **真實資料（KITTI）驗證現象泛化**（見 Q9）。單靠 CARLA + 漸進差異，偏 mid-tier。

---

## Q5. threshold / robustness 是否支持結論？
**強力支持。**（`PAPER2_V5_THRESHOLD_ROBUSTNESS.md`，掃 pos{2,3,5}×spd{2,3,5}×dir{30,45,60}=27 組）
- R1 velocity_valid < position_valid（每 bin）：**27/27**
- R2 velocity_valid 隨距離單調崩潰：**27/27**
- R3 position_only ≥0.20（中/近）：**27/27**
- R4 近距 velocity_valid <0.70：**27/27**
- velocity_valid 範圍 0-15m [0.32,0.43] / 30m+ [0.04,0.11] → 絕對值隨閾值移動，但**排序與崩潰不變**。→ 核心現象**非調閾值調出來的**。

---

## Q6. refusal policy 是否真的比 naive baseline 好？
**分兩層，誠實：**
- **vs no-policy（永遠估速度）：是，大勝。** overconfident-wrong-velocity 0.839 → ~0.58-0.66（隨 retention）。這是 validity-layer 的核心價值。
- **vs naive distance gate：大致打平（wash）。** trade-off 曲線交叉：retention 0.7 distance 較好(0.58 vs 0.66)、0.9 OVI 較好(0.64 vs 0.72)。→ **「我們的 scorer 勝 distance」站不住**，但「observability-aware refusal（即使是 distance/geometry gate）+ multi-class + decision-level 評估」這個**框架**站得住，且「簡單 gate 已夠用」是誠實有用的訊息。
- 參考：v4 NOUE policy 0.586→0.387（不同 split，不可直比）。

---

## Q7. v5 是否足以成為期刊主軸？
**誠實判斷：足以成為一篇紮實的 measurement + methodology 論文，但屬 mid-tier，非 breakthrough；且目前最好先補真實資料。**
- **撐得起的核心**：velocity-unobservability 現象（robust）+ position/velocity validity 分離 + multi-class refusal + decision-level evaluation + 清楚的 claim boundary。
- **撐不起 top-tier 的原因**：方法新穎性薄（OVI marginal、Qiu 2018 先行）；單一模擬平台（CARLA）；raw velocity = centroid-diff（noisy）。
- → 主軸成立，但**故事重心要放在「現象 + 決策框架」，不是「新 index」**。

---

## Q8. 建議投哪裡？
- **現狀（CARLA-only）可投**：IEEE **IV** / **ITSC**（會議，intelligent vehicles，最契合）；或 **IEEE Sensors Journal / MDPI Sensors**（期刊，框成 sensor-perception reliability）。
- **補 KITTI 真實資料 + per-regime 後可衝**：**IEEE RA-L**（簡潔 + 應用）、或 **T-IV / T-ITS**（需更強系統/真實驗證）。
- **不建議**：CVPR/ICCV/ICRA main（方法新穎性不足）。
- 投稿前以校內資料庫核對 JCR/SCImago 年度分區。

---

## Q9. 還缺哪些實驗、圖、表？
**最高價值（決定能否升級 venue）：**
1. **★ KITTI tracking 真實資料驗證**（image_2/3 已下載完成）：在 KITTI 跑物體 pipeline + label_02 GT → 證明 velocity-unobservability 現象 + validity layer **泛化到真實資料**。這是把 mid-tier 推向 RA-L/T-IV 的關鍵。**需寫 KITTI tracking reader（現有 runner 吃不了 tracking 佈局）+ 物體 validity on real labels。**
2. **per-regime 細分**（car-following / lateral-crossing / occlusion / high ego-yaw-rate）：需場景標註（可由 GT bearing/relative-heading 自動導出）→ 強化 C1 phase map。
3. **cleaner velocity estimator ablation**（光流/RAFT vs centroid-diff）：證明 velocity unobservability **不是只是我們估計器太爛**——這是 reviewer 必問。
4. **missed-danger / safety metric**（近距 high-risk 物體被正確 warning 的比例）。

**圖（有 4 / 缺）：** 有 validity-by-distance、phase-map heatmap、OVI-within-bin、refusal-trade-off。缺 KITTI-vs-CARLA validity、per-scenario validity、failure gallery、missed-danger curve。
**表（有 / 缺）：** 有 validity-by-bin/density/town、threshold-robustness、OVI-ablation、refusal-policy+trade-off、claim-boundary。缺 per-regime validity、KITTI validity、cleaner-velocity ablation。

---

## Q10. 下一步是否可以開始正式論文初稿？
**部分可以，建議分兩段：**
- **現在可起草**：Intro、Related Work（claim boundary 已備）、Problem Formulation、C1（phase map + robustness）、C3（refusal layer + trade-off）。這些證據已足、誠實、reviewer-proof。
- **起草前/同時應補（gate 在你的 checkpoint 決策）**：(a) **KITTI 真實資料 validity**（最關鍵，決定 venue 與說服力）；(b) 決定 **OVI 去留**（建議降為 minor 或移 appendix）；(c) per-regime 場景標註；(d) cleaner-velocity ablation。
- **我的建議**：先批准 **KITTI 真實資料驗證**（資料已在），它最能把這篇從「CARLA-only mid-tier」升級。其餘（per-regime、cleaner velocity）為加分。

---

## Claim-boundary 一覽（投稿用，`PAPER2_V5_LITERATURE_POSITIONING.md` 為全本）
| 方法 | 他們做什麼 | 我們**不可** claim | 我們**可** claim |
|---|---|---|---|
| **Qiu IROS2018**（最近威脅）| 單物體 VI metric pose + scalar observability 拒絕(4 退化) | first observability gating / 首次拒絕物體狀態 | regime phase map + pos/vel 分離 + 5-way refusal + decision-level eval |
| VDO-SLAM / DynaSLAM II / ClusterVO / DOT-SLAM | 永遠輸出 object SE(3) velocity，不 gate | 比他們估得準 | 我們 decide-then-estimate（他們 estimate-and-hope）|
| DynaVINS / IDY-VINS | 剔除動態特徵護 ego | 物體狀態相關貢獻 | 正交（不同問題）|
| MonoRUn / Gaussian-YOLO / BayesOD | object pose covariance / uncertainty | OVI 是新 uncertainty | 我們做 **validity decision/regime**，非又一個 uncertainty number |
| SelectiveNet / risk-coverage | selective prediction 框架 | 發明 abstain | 借用 abstain 框架到 object-state observability |
| Task-Aware Risk (RSS2023) | 失敗的 task-relevance | 同類 | 互補（我們是幾何 observability，非 task-relevance）|
| Conformal risk tube (Fu&Chen ICRA2026) | risk-importance + conformal coverage | 以 conformal 為創新 | 明確區隔（幾何 state-validity ≠ risk scoring）|
| bearings-only TMA (1981) | velocity 不可觀測理論 | observability insight 是新的 | 引為 foundation；新在 deployable road validity layer |

---

## 最終誠實定論
- **v5 是真論文，但是 modest 的 measurement+methodology 論文。** 脊椎 = C1（robust velocity-unobservability 現象 + regime map）+ C3（validity/refusal layer + decision-level eval）。
- **OVI(C2) 誠實 marginal、ego-diagnostic(C4) null、VINS-conditioning(v4 A2) 負** —— 全部照實寫，反而增加可信度。
- **升級關鍵 = KITTI 真實資料驗證（資料已下載）。** 
- **STOP — 等你 design checkpoint：** (1) 是否批准 KITTI 真實資料驗證？(2) OVI 去留？(3) 鎖定 venue（IV/ITSC/Sensors 現投，或補 KITTI 衝 RA-L/T-IV）？(4) 是否開始起草 Intro/Related/C1/C3？
