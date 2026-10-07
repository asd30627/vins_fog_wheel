# PAPER2 — TCSV METHOD FORMALIZATION

> **TCSV = Temporal-Consistency Selective Validator.** 把 C2 從「10 特徵 + HistGBM」形式化成一個明確的方法：
> **selective prediction（learning-to-refuse）over object velocity estimates**，用 runtime-observable 的時序自洽性殘差，
> 以 **risk-coverage / selective-risk** 為目標與評估。**非初稿；非換方向。** 全程無 GT 進特徵，只有 label 用 GT。
> 紅線：不碰 VINS backend、不加 object factor、不做 frontier/trajectory planning、無 transformer/attention/大模型。
> 日期 2026-06-30。實測結果見 `PAPER2_TCSV_RESULTS.md`，故事整合與誠實裁示見 `PAPER2_TCSV_STORY_UPDATE.md`。

---

## 1. Problem statement（selective velocity validity）

對每個被偵測到的動態物體軌跡點 $t$，前端產生 raw 狀態估計 $\hat{s}_t=(\hat{p}_t,\hat{v}_t)$。
定義 ground-truth velocity validity（label，只在評估用 GT）：

$$y_t = \mathbb{1}\big[\,\|\hat v_t - v_t^{\text{gt}}\| \le \tau_v\,\big],\quad \tau_v = 3\text{ m/s (ego-independent)}.$$

**Selective validator** 學一個信心分數 $g_\theta(x_t)\in[0,1]$ 與一個 emit 門檻 $\rho$：

$$
\text{decision}(t)=
\begin{cases}
\textbf{emit velocity} & g_\theta(x_t)\ge\rho\\
\textbf{refuse (position-only)} & g_\theta(x_t)<\rho
\end{cases}
$$

其中 $x_t$ **只用 runtime-observable 量**（無 GT、無 backend 內部量）。
目標不是最大化分類 accuracy，而是 **在「保留多少 valid velocity（coverage / retention）」與「emit 出去的 overconfident-wrong velocity（risk）」之間取得最好的 trade-off**。這把問題正式放進 *selective prediction / learning-to-defer* 的框架，而不只是二元分類。

---

## 2. Feature formalization（time-windowed temporal self-consistency）

特徵分三組（共 14；window $W$ 控制 4 個 windowed 特徵）：

**GEO（5）** `range_m, bearing_deg, bbox_area, depth_m, det_conf` — 幾何/外觀。

**TEMP-base（2）** `track_age, raw_speed` — 軌跡壽命與 raw 速度大小。

**TEMP-residual（7，本篇形式化的核心）** — 全部來自 raw 偵測序列，physically-motivated：

| feature | 定義（$dt$=CARLA 0.05 / KITTI 0.1） | 物理意義 |
|---|---|---|
| `cv_residual` | $\|\hat p_t-(\hat p_{t-1}+\hat v_{t-1}dt)\|$ | 等速模型預測誤差：raw 軌跡是否自洽 |
| `acceleration_score` | $\|\hat a_t\|=\|(\hat v_t-\hat v_{t-1})/dt\|$ | 瞬時加速度量級 |
| `jerk_score` | $\|\hat a_t-\hat a_{t-1}\|/dt$ | jerk：估計的高階抖動 |
| `velocity_direction_flip_count` | 最近 $W$ 個 transition 中 heading 反轉 $>90°$ 的次數 | 方向亂跳 = 不可信 |
| `bbox_depth_consistency` | 最近 $W$ 對中 $\text{sign}(\Delta\log\text{area})=\text{sign}(-\Delta\text{depth})$ 的比例 | 趨近時 bbox 應變大、depth 應變小（物理一致性） |
| `short_window_position_jitter` | $\text{std}$ of `cv_residual` over last $W$ frames | 位置殘差的視窗抖動 |
| `short_window_velocity_jitter` | $\text{std}$ of `raw_speed` over last $W$ frames | 速度的視窗抖動 |

- 只用連續 frame（$\Delta\text{frame}=1$）算微分量，gap 不產生假速度。
- $W=1$ 會讓 4 個 windowed 特徵退化（測「視窗聚合是否真有用」）。
- **無洩漏**：以上皆 runtime 可觀測；GT 只進 label $y_t$。

---

## 3. Model family（刻意極簡，無花招）

| 版本 | 形式 | 角色 |
|---|---|---|
| **TCSV-rule** | depth-3 decision tree（min_leaf=200, class-balanced）| 可解釋 rule gate；輸出人類可讀規則 |
| **TCSV-HistGBM** | HistGradientBoosting（max_iter=300, depth=4, lr=0.05, l2=1.0）| 主模型 |
| **TCSV-MLP** | (64,32) MLP，early-stopping，standardized | neural 對照 |

對照 baseline：`no_policy`（全 emit）、`distance_gate`（$-\text{range}$）、`OVI_geom`（logistic on geometry）。
**明確不做**：transformer、attention、sequence model、大型深度網路。

---

## 4. Selective-risk objective & operating evaluation（方法感的真正來源）

不只報 AUROC。以 selective prediction 的標準量化：

- **Risk–coverage curve**：把樣本按 $g_\theta$ 由高到低排序，coverage = emit 比例，risk = emit 中 overconfident-wrong velocity 比例。
- **AURC**（area under risk-coverage，↓ 越低越好）= 選擇性拒絕品質的單一摘要。
- **Overconfident-wrong velocity @ fixed retention = 0.8 / 0.9**：強制保留 80%/90% 的 valid velocity 時，emit 出去的錯誤速度率——這是 planner 真正在意的「我保住覆蓋率時還會被騙多少」。
- 並列：overconf、retention、false_refusal、F1_invalid（operating point 用 train-Youden）。

> 設計理由：分類 AUROC 高 ≠ 適合拒絕。AURC 與 overconf@retention 直接衡量「當作 refusal gate 用時」的安全-覆蓋取捨，這是把 C2 從 classifier 提升成 **selective validator** 的關鍵，也是審稿人能認的「方法」而非「調包」。

---

## 5. Evaluation protocol（防洩漏 / 防發散）

- **Split**：CARLA by **run**、KITTI by **sequence**，cross-dataset（CARLA→KITTI、CARLA+KITtrain→held-out-KITTI）。**永不 frame-random。**
- **Grouping fix**：temporal 特徵以 `(town, run, track_id)`（CARLA）/`(seq, track_id)`（KITTI）分組——修正前作 `(run, track_id)` 跨 town 混軌的問題（見 story update §「honest corrections」）。
- **Ablations**：(a) NEW residual vs prior OLD10、(b) permutation importance（GEO / TEMP-base / TEMP-resid 分組 + per-feature）、(c) window $W\in\{1,3,5,7\}$。
- **Artifacts**：`scripts/paper2_tcsv_features.py`、`scripts/paper2_tcsv_train_eval.py`、`paper2_tcsv_metrics.csv`、`paper2_tcsv_riskcov.csv`、`paper2_tcsv_window_ablation.csv`、`paper2_tcsv_importance.csv`、`figs/fig_tcsv_riskcov.png`。

---

## 6. 與既有貢獻的關係

- **C1（現象）不變。**
- **C2（temporal-consistency selective model）= 本篇 TCSV 的形式化對象**：把它從「特徵清單 + 分類器」升級為「selective-prediction 問題 + 物理化殘差 + risk-coverage 目標」。
- **C3（refusal-aware policy）= TCSV 的 operating-point 評估**：risk-coverage / overconf@retention 就是 decision-level 量化。

> **誠實前提**：本形式化的「方法價值」主要來自 **問題重構 + selective-risk 評估**，不是宣稱新特徵贏舊特徵。實測新 residual 對結果是中性（KITTI 微升、CARLA 微降）；詳見 `PAPER2_TCSV_RESULTS.md` §2–§4 與 `PAPER2_TCSV_STORY_UPDATE.md`。
