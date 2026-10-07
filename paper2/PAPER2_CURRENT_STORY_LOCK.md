# PAPER2 — CURRENT STORY LOCK (v2)

> **目的**：固定 Paper-2 的論文邊界，防止題目繼續發散。**這不是論文初稿**，是 story lock。
> **主題**：**Temporal-Consistency-Aware Selective Object State Validity for GPS-Denied Navigation**
> **依據**：`PAPER2_V5_MODEL_UPGRADE_DECISION.md`、`PAPER2_SELECTIVE_VALIDITY_RESULTS.md`、`PAPER2_KITTI_TRACKING_VALIDITY_RESULTS.md`、`PAPER2_CARLA_COLLISION_AUDIT.md`
> **檔次定位**：mid-tier（IEEE IV / ITSC / RA-L / T-IV）站得住。
> **日期**：2026-06-30

---

## 1. 最終問題定義

在 **GPS-denied** 導航情境下，自車用 VIO 估計周圍**動態物體的狀態（position / velocity）**時，這些估計**何時可信、何時該拒絕（refuse）**？

- 核心觀察：物體 **velocity** 估計隨幾何（距離）崩潰，但 **position** 較穩 → 存在一個 **position-only regime**（位置可用、速度不可信）。
- 核心方法問題：能否用**只在 runtime 可觀測、不需 GT** 的訊號，學出一個 selective validity 判斷，**贏過單純的 distance / geometry 門檻**？
- 答案（本篇主張）：能。而且關鍵訊號**不是距離/幾何，是 raw 估計自身的時序自洽性（temporal-consistency）**——抖動/物理不合理的 raw 速度 = 不可信。

**一句話**：本篇做的是「**動態物體狀態估計的可信度判斷與拒絕策略**」，不是物體狀態估計本身、不是定位、不是規劃。

---

## 2. 非本篇範圍（明確排除）

以下**全部不是 Paper-2 的貢獻**，寫稿時不得 claim：

- ❌ **不做 frontier planning method**（frontier 只能當 downstream demo，見第 7 節）
- ❌ **不做 trajectory planning method**
- ❌ **不改 VINS backend**（紅線；未碰 backend/factor/G3）
- ❌ **不加 object factor**（不把物體塞進 VINS 後端 BA）
- ❌ **不 claim 改善 localization / ego ATE**（本篇不主張提升自車定位精度）

> 這些守住，論文邊界才不會再爆。任何「順便也改善了定位/規劃」的句子都要刪。

---

## 3. 三個最終貢獻（鎖定）

### C1 — CARLA+KITTI object velocity-validity phenomenon（地基）
- velocity 隨距離崩潰、position 較穩、**position-only regime 真實存在**、invalid-velocity 常見（refusal 有意義）。
- **跨資料集成立**：4 個現象在真實 KITTI 全部重現（CARLA vel_valid 0.70/0.26/0.08 vs KITTI 0.65/0.45/0.21；絕對值不同但趨勢一致）。
- **threshold-robust**（27/27）、**near-contact-robust**：排除 3.8% near-contact frame 後趨勢不變（velocity_valid by bin 0.38/0.16/0.07 不變，position 近距略升）→ **不是碰撞 artifact**。

### C2 — Temporal-consistency selective validity model（方法新意）
- learned selective validity，**4/4 scenario 贏 distance gate**（AUROC）。
- **核心洞見**：增益由 **temporal-consistency 特徵驅動**，不是幾何/距離。
  - CARLA: distance 0.755 / GEO-only 0.723 / **TEMP-only 0.806** / GEO+TEMP 0.864
  - KITTI: distance 0.686 / GEO-only 0.814 / **TEMP-only 0.879** / GEO+TEMP 0.928
- 特徵全部 runtime-observable，只有 label（vel_err≤3）用 GT → **無洩漏**（待第 6 節正式 audit 釘死）。

### C3 — Refusal-aware state policy / planner-facing evaluation（落地價值）
- 多類輸出：full-state / position-only / invalid-velocity / unobservable / warning。
- **decision-level 評估**：overconfident-wrong-velocity、false-refusal、valid-retention、F1_invalid（不只看 AUROC）。
- 例：HistGBM 把 CARLA overconfident-wrong-velocity 0.761→0.605（retention 有代價但 refusal 確實有效）。

---

## 4. 最終模型架構

```
前端 raw 物體狀態估計（CARLA dynamic_v3 / KITTI tracking, YOLOv8m + depth）
        │
        ▼
  10 個 runtime-observable 特徵（無 GT）
  ┌─ GEO 幾何：range_m, bearing_deg, bbox_area, depth_m, det_conf
  └─ TEMP 時序：track_age, raw_speed, raw_accel, vel_smooth, bearing_change   ← 主訊號
        │
        ▼
  Selective Validity Network（主力 = HistGBM；對照 = logistic / MLP）
        │
        ▼
  validity 分數 → Refusal-aware policy 分流
  full-state / position-only / invalid-velocity / unobservable / warning
        │
        ▼
  decision-level 評估（overconf / retention / false_refusal / F1_invalid）
```

- **Label**：`vel_err = ||raw_vel − gt_vel|| ≤ 3 m/s`（ego-independent，ego-motion 相消）。
- **Split 嚴謹度**：CARLA **by run**、KITTI **by sequence**（**不是 frame random**）。
- **資料量**：CARLA n=15811、KITTI n=37022（34943 有 velocity，21 seqs）。

**核心數據（AUROC, velocity_valid）**

| scenario | distance_gate | best selective | Δ | verdict |
|---|---|---|---|---|
| CARLA→CARLA (run) | 0.755 | 0.873 (HistGBM) | +0.117 | BEATS |
| KITTI→KITTI (seq) | 0.686 | 0.924 (MLP) | +0.238 | BEATS |
| CARLA+KITtrain→held-out-KITTI | 0.686 | 0.906 (HistGBM) | +0.220 | BEATS |
| CARLA→KITTI（直接遷移）| 0.713 | 0.747 (logistic) | +0.034 | ⚠️ 弱（需 target 校準）|

---

## 5. baseline 清單（鎖定）

| baseline | 角色 |
|---|---|
| **no policy**（全收，base invalid rate）| 下限參考（CARLA overconf 0.761 / KITTI 0.544）|
| **distance gate** | 主要對照（Qiu-style 幾何門檻的最簡形式）|
| **OVI geometry**（OVI_geom）| 幾何 observability 門檻（marginal，Δ≈+0.008，證明幾何不夠）|
| **selective_logistic** | 學習式線性對照 |
| **selective_mlp** | 學習式非線性對照 |
| **selective_hist_gbm** | **主力模型** |

> （`selective_logistic_interact` 為內部探索變體，論文中可省或併入 logistic 討論。）

---

## 6. 必須補的驗證（投稿前）

| # | 項目 | 為什麼必要 | 優先序 |
|---|---|---|---|
| V1 | **stereo KITTI redo** | 目前 KITTI 用 monocular bbox-height depth（image_03 zip 曾損壞，aria2c 重抓 ~95%）；改 stereo → 與 CARLA apples-to-apples、去 class-height prior 的 noisy velocity | 高 |
| V2 | **SHAP / permutation importance** | 把「temporal-consistency 是主訊號」從 ablation 升級到 per-feature 釘死 | 高 |
| V3 | **leakage audit** | 正式證明 10 個特徵全 runtime-observable、label 才用 GT（reviewer 必問）| 高 |
| V4 | **temporal window ablation** | 時序特徵用多長 window（track_age / vel_smooth 的時間尺度敏感度）| 中 |
| V5 | **planner-facing minimal evaluation** | 用 refusal 後的狀態餵一個**最小** downstream 判斷，證明 policy 對下游有用（**最小**，不是做 planner method）| 中 |

> 這 5 項是把 mid-tier 釘穩的最小集合。**不在此清單的，不要開新坑。**

---

## 7. frontier 的定位（嚴格約束）

- frontier **只能作為 downstream validation / 國科會 demo**（呈現「拒絕不可信物體後，下游使用更安全」）。
- frontier **不能變成本篇主貢獻**——本篇主貢獻是 C1/C2/C3，frontier 出現在 paper 中至多是 V5 的「planner-facing minimal evaluation」插圖等級。
- 若要做**完整 frontier exploration + trajectory planning method** → **另開 Paper-3**，不污染 Paper-2。

---

## 8. 一段安全的 paper narrative（內部用，非初稿）

> 在 GPS-denied 導航中，自車需估計周圍動態物體的位置與速度，但這些估計的可信度差異極大。我們在 CARLA 與真實 KITTI 上實證：物體**速度**估計隨距離崩潰、**位置**較穩，存在一個可用的 **position-only regime**（C1，且非碰撞 artifact、跨資料集成立）。基於此，我們提出一個 **selective object state validity** 模型，僅用 runtime 可觀測特徵判斷估計是否可信，並在嚴格 split 下**贏過 distance / geometry 門檻**；關鍵洞見是——**最強的可信度訊號不是距離或幾何，而是 raw 估計自身的時序自洽性**（C2）。最後我們把它包成一個 **refusal-aware state policy**，以 decision-level 指標（overconfident-wrong-velocity、retention、false-refusal）評估，顯示拒絕層確實降低高風險的錯誤速度輸出（C3）。我們**不修改 VIO 後端、不加 object factor、不主張改善自車定位**——本篇是物體狀態估計的**可信度判斷與拒絕**，與 Qiu 2018 的幾何門檻 binary 拒絕形成實質方法差異。

## 9. 一段給國科會成果整合的 narrative（內部用）

> 本子題建立了 GPS-denied 下動態物體狀態估計的**可信度評估與拒絕機制**：在合成（CARLA）與真實（KITTI）資料上驗證「速度隨幾何崩潰、位置較穩」的現象，並提出以**時序自洽性**為核心訊號的 learned selective validity 模型，於嚴格資料切分下優於距離/幾何基準。此機制可作為上層導航（含 frontier 探索 demo）的**安全前處理**：把不可信的物體速度標記為拒絕，避免下游規劃採信錯誤動態資訊。完整的 frontier + 軌跡規劃為後續子題（Paper-3）規劃方向，本期成果聚焦於**可信度判斷層**的建立與跨資料集驗證。

---

## 10. 「不要做什麼」紅線

- 🚫 不寫正式論文初稿（這次只做 story lock）。
- 🚫 不開 frontier planning / trajectory planning 的方法坑（→ Paper-3）。
- 🚫 不碰 VINS backend / factor / G3；不加 object factor。
- 🚫 不 claim 改善 localization / ego ATE。
- 🚫 不重錄 CARLA（紅線）。
- 🚫 不在 V1–V5 清單外新增「順手再做一個」的驗證或模型變體。
- 🚫 不把 cross-dataset 弱遷移（+0.034）包裝成強泛化——誠實標註需 target 校準。
- 🚫 不超賣 OVI（幾何 marginal，是對照組不是賣點）。

---

**STORY LOCK v2 完成。邊界已固定：問題=物體狀態可信度判斷+拒絕；貢獻=C1/C2/C3；模型=temporal-consistency selective validity；frontier=downstream demo only。下一步等你裁示（補 V1–V5 哪一項，或先停）。**
