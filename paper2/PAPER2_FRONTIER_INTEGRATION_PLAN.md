# PAPER2_FRONTIER_INTEGRATION_PLAN — Adapter-first 整合計畫

> 紅線：**不大改 frontier 原始碼、不碰 VINS backend、不加 object factor、不宣稱新 planner。**
> 策略：**adapter 旁掛**，把 Paper-2 validity 翻譯成 frontier/Nav2 已經懂的訊號。

---

## 1. 架構總覽

```
[Paper-2 V5 selective validity]   (offline model / replay)
            │  per-object: class ∈ {full_state, position_only,
            │              invalid_velocity, unobservable, conservative_warning}
            │              + pos, vel(若有), confidence
            ▼
   (NEW) validity_publisher_node  ──►  /object_validity   [自訂 msg 或 vision_msgs/Detection3DArray + 欄位]
            │
            ▼
   (NEW) validity_to_nav_adapter  ──►  翻譯規則（§4）
            ├─►  /dynamic_obstacle_layer   (PointCloud2 / costmap_filter mask)   ← 進 Nav2 local_costmap
            ├─►  /frontier_risk_cost        (std_msgs/Float32 或 Bool)            ← 影響 frontier 選點 / 降速
            └─►  /path_cost_monitor/high_cost  (既有 Bool risk-bus)               ← 觸發既有安全停/換點行為
                                  │
                                  ▼
                      [現成 wavefront_explorer + Nav2]  ← 不改核心
```

**兩個新 node，零修改 frontier 既有 node。** 全部走「新 topic + 既有 risk-bus + 官方 costmap_filter」三條注入路徑。

---

## 2. 為什麼是 adapter，不改 planner

- frontier 已有 **risk-bus**：`/path_cost_monitor/high_cost`（→ `twist_servo` 安全停、`goal_repeater` 換 frontier 點）。我們餵這條就能改行為。
- Nav2 已有官方 **costmap_filters**（`KeepoutFilter` / `SpeedFilter`）與 **層式 costmap**（可加一個 `dynamic_obstacle_layer`），**不需改 planner code**，只改 param yaml 把新層/filter 掛上。
- 因此 Paper-2 的工作邊界＝「**產生正確的 validity → 翻成對的 mask/cost/limit**」，而非 planning 演算法。**這保住了「frontier 不是主貢獻」的定位。**

---

## 3. 新增元件規格（Phase 1 才實作）

### 3.1 `validity_publisher_node`（輸入端，補 audit G1）
- 來源二選一：
  - **(a) replay**：讀 Paper-2 V5 輸出 CSV（per-frame per-object class+pos+vel），按時間戳 publish。最快、最可控，**建議 demo 首選**。
  - **(b) inference**：載入 `paper2_train_selective_validity.py` 訓練的模型，吃 live 物件 track → 即時分類。stretch。
- 輸出 `/object_validity`：建議 **自訂 msg**（最小欄位）：
  ```
  ObjectValidity[] objects
    int32   id
    uint8   validity_class   # 0 full_state,1 position_only,2 invalid_velocity,3 unobservable,4 conservative_warning
    geometry_msgs/Point     position
    geometry_msgs/Vector3   velocity     # 僅 class==full_state 才可信
    float32 confidence
  std_msgs/Header header   # frame_id 對齊 odom/map
  ```
  （或復用 `vision_msgs/Detection3DArray` + `results[].hypothesis` 塞 class，避免自訂 msg 編譯；二選一，Phase 1 決定。）

### 3.2 `validity_to_nav_adapter`（翻譯端）
- sub `/object_validity` → 套 §4 規則 → pub 三條下游。
- **唯一含 Paper-2 語意的決策都集中在這裡**（好處：可單測、可 ablation、不污染 frontier）。

---

## 4. validity → planner 轉換規則（核心表）

| validity_class | 幾何含意 | adapter 動作 | 下游 topic |
|---|---|---|---|
| **full_state** | pos+vel 皆可信 | 用 **position + velocity 短時預測**（predict t∈[0,τ] 掃出佔據走廊）寫入 dynamic layer | `/dynamic_obstacle_layer`（含預測佔據） |
| **position_only** | 位置可信、速度不可信（多為靜止或退化） | **只當「當前障礙物」**，**不做速度預測**；正常 inflation | `/dynamic_obstacle_layer`（僅當前位置） |
| **invalid_velocity** | 有物體、速度錯 | **禁止 velocity prediction** + **加大 inflation**（保守半徑） | `/dynamic_obstacle_layer`（放大 footprint） |
| **conservative_warning** | 低信心 / 邊界 | 提高 `/frontier_risk_cost` → **降速**、frontier 選點避開該區 | `/frontier_risk_cost`(↑) |
| **unobservable** | 速度結構性不可觀測 | 同 warning + 必要時觸發既有安全 **保守避開** | `/frontier_risk_cost`(↑) (+ 可選 `/path_cost_monitor/high_cost`) |

> 設計準則：**class 越不可信 → 行為越保守（不預測、放大、降速、避開）**，且**所有「速度預測」只在 `full_state` 開啟**。這正是 Paper-2「decide-then-estimate」的下游體現。

### 預測/inflation 參數（建議起始值，須 ablation）
- `τ_predict = 1.0 s`（full_state 預測 horizon）
- `inflation_base = 0.30 m`，`inflation_invalid_vel = 0.60 m`
- `risk_cost_warning = 0.6`，`risk_cost_unobservable = 0.9`（0~1，映射到 SpeedFilter 限速 / frontier 罰分）
- 三組 baseline **共用同一組參數**，只差「validity 來源」，確保公平。

---

## 5. 三組 baseline（差異只在 validity 來源，planner/參數相同）

| Baseline | validity 來源 | 行為 |
|---|---|---|
| **A. always-full-state** | 所有 object 強制 `full_state` | 全部都 position+velocity 預測（樂觀；會接受錯誤速度） |
| **B. distance gate** | 只用距離門檻：`d<d0`→full_state，否則 position_only | 只靠距離判速度可信度（無時間一致性、無觀測性） |
| **C. ours** | Paper-2 selective validity + refusal policy | 5-class + refusal，§4 規則 |

> A、B、C **共用** `validity_to_nav_adapter` 的同一套 §4 翻譯，只是上游 class 不同 → 隔離出「validity 品質」這一個變因。

---

## 6. 落地步驟（Phase 1，待裁示後才動）

1. **先讓原版 frontier 在選定場景 A→B 成功**（無 Paper-2，驗 audit G5）。← gate，不過不往下。
2. 加 `validity_publisher_node`（replay 模式）。
3. 加 `validity_to_nav_adapter` + 在 Nav2 param yaml 掛 `dynamic_obstacle_layer` / `SpeedFilter`（**改 yaml，不改 planner code**）。
4. 接既有 risk-bus（`high_cost` / `frontier_risk_cost`）。
5. 跑 baseline A / B / C × 場景變體（見 eval protocol）。

---

## 7. 不做清單（紅線複述）

- ✗ 不改 `wavefront_frontier.py` 核心選點演算法（只新增旁掛 node 與 param）。
- ✗ 不碰 VINS / estimator backend；GPS-denied 定位只在 `/odom` 介面換源，不進 backend。
- ✗ 不加 object factor 到任何 BA / factor graph。
- ✗ 不宣稱提出新 frontier planner；frontier 全程是現成 downstream。
- ✗ adapter 若擋不住某退化情況，誠實記為 limitation，不在 planner 裡硬補。

---

## 8. 風險與緩解

| 風險 | 緩解 |
|---|---|
| 自訂 msg 編譯麻煩 | 改用 `vision_msgs`（已在 ROS2 生態）承載 class |
| dynamic layer 與 frontier 的 unknown 區互相干擾 | dynamic layer 只寫 local_costmap，frontier 仍讀 `/map`，職責分離 |
| replay 時間戳對不上 live odom | publisher 以 sim_time 對齊；demo 用同一 bag/sim clock |
| 「validity 影響行為」訊號太弱看不出差異 | 用場景 V2（退化動態 D2）放大 baseline A 的錯誤 |
