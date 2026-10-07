# PAPER2_FRONTIER_EVAL_PROTOCOL — Downstream 評估協定

> 目的：證明 **Paper-2 selective validity（C, ours）** 在真實導航決策上**優於** always-full-state（A）與 distance-gate（B）。
> frontier/Nav2 是**固定的測試載體**（三組共用），唯一變因 = validity 來源。

---

## 1. 實驗設計

- 因子：`validity_source ∈ {A always-full, B distance-gate, C ours}`。
- 場景變體：`V0 靜態 / V1 單動態 / V2 退化動態★ / V3 雙動態`（見 scenario §6）。
- 重複：每 (source × variant) **N ≥ 10 trials**，亂數種子 / 動態相位不同但**三組之間配對相同**（paired，同 seed 同初始）。
- 控制變數：planner、costmap 參數、§4 翻譯規則、`τ_predict`、inflation、`T_max` **全部固定一致**。
- clock：統一 `use_sim_time`，同一 sim/bag 時鐘。

---

## 2. 指標定義（全部要可從 rosbag 自動算）

### 2.1 任務層
| 指標 | 定義 | 方向 |
|---|---|---|
| **success rate** | 滿足 scenario S1∧S2∧S3 的 trial 比例 | ↑ |
| **time-to-goal** | A→B 抵達耗時（僅成功 trial） | ↓ |
| **path length** | 實際走行軌跡長度 | ↓（過長=亂繞） |

### 2.2 安全層
| 指標 | 定義 | 方向 |
|---|---|---|
| **collision** | footprint 與障礙/動態物實際相交次數 | ↓ |
| **near-collision** | 最小間距 < `d_safe`(預設 0.2 m) 的事件數 | ↓ |
| **unnecessary stop** | 觸發安全停但當下**無真實碰撞風險**（GT 距離 > `d_clear`）的次數 | ↓ |

### 2.3 Validity 決策層（Paper-2 核心，連到 V5 refusal 指標）
| 指標 | 定義 | 方向 | 對應 |
|---|---|---|---|
| **false dynamic-obstacle warning** | 對**靜止/無威脅**物體發出動態警示/讓行 | ↓ | B 應較差（純距離） |
| **planner blocked ratio** | planner 回 `no valid path` 的時間佔比 | ↓ | 過度保守會升高 |
| **replan count** | 重新規劃次數 | ↓（過高=決策抖動） | |
| **overconfident wrong velocity accepted** | planner 採用了 GT 判定為**錯誤**的 velocity 的次數（A 預期最高）★ | ↓ | = V5 `overconfident_wrong_vel` 的下游版 |
| **valid velocity retention** | GT 可信速度中，被 C 正確當 full_state 使用的比例 | ↑ | = V5 `valid_retention` 下游版 |

★ **overconfident wrong velocity accepted** 與 **valid velocity retention** 是把 Paper-2 V5 的離線決策指標（overconfident_wrong 0.84→0.64、retention 0.904）**搬到閉環導航**的證據，是本 demo 對論文的主回饋。

---

## 3. 預期結果（hypothesis，用來判斷 demo 是否「講得通」）

| 指標 | A always-full | B distance-gate | C ours |
|---|---|---|---|
| success rate (V2★) | 中（偶因錯速度誤判讓行/搶行而失敗或撞） | 中 | **高** |
| overconfident wrong vel accepted | **高** | 中 | **低** |
| valid velocity retention | 高（但含錯的） | 低（距離一刀切砍掉可信速度） | **高且乾淨** |
| false dynamic warning | 低（全信→不警示） | **高** | 低 |
| unnecessary stop | 低 | 高 | 低 |
| near-collision (V2) | **高** | 中 | 低 |

> 若 C 在 V2 上**沒有**同時改善 overconfident-wrong 與 near-collision，則 demo 不支持論文 claim → **誠實回報，不調參硬湊**（遵守 gated-execution-discipline）。

---

## 4. 統計與報告

- 主檢定：C vs A、C vs B，paired（同 seed）；success rate 用 McNemar，連續指標用 Wilcoxon signed-rank。
- 每指標報 median + IQR + n；成功率報比例 + Wilson CI。
- **V0 sanity**：三組 success 應接近 100%；若 C 在 V0 退步 → 代表 adapter 把無害情況搞保守，須先修。
- 輸出：`paper2_frontier_eval_metrics.csv`（每 trial 一列）＋ 彙整表 + 圖（success bar、overconfident-vel bar、軌跡疊圖）。

---

## 5. 量測工具（Phase 1 才寫，列需求）

| 需求 | 來源 |
|---|---|
| robot 軌跡 | `/odom`（path length、抵達判定） |
| 碰撞/間距 | 模擬器 GT 物件位姿 vs footprint（需 sim 提供 GT） |
| validity 接受紀錄 | `validity_to_nav_adapter` log（哪個 class、是否做了 vel 預測） |
| GT velocity 對錯 | 模擬器 actor GT 速度 vs validity 給的速度（沿用 V5 `speed_err≤3 ∧ dir_err≤45°` 判準） |
| planner blocked / replan | Nav2 BT / planner 狀態 topic |

> **依賴**：碰撞與 overconfident-velocity 指標**需要模擬器 ground-truth**（物件真位置/真速度）。bag-only 無 GT 則這些指標退化為近似（須在報告標註）。

---

## 6. 公平性紅線

- 三組唯一差異 = validity class 來源；**禁止**為 C 單獨調 planner/inflation/τ。
- B 的 `d0` 距離門檻須**獨立合理化**（例如取 V5 distance-bin 的中位轉折），不能挑對 C 有利的值。
- 任一指標若 A/B 因實作 bug 異常差，須修到「強 baseline」再比（避免打稻草人，延續 FAIRNESS_REVIEW 精神）。
- 所有「partial scene / 近似 GT / 未跑滿 N」一律在報告誠實標註。
