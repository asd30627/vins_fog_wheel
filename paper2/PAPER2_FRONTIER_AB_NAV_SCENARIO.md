# PAPER2_FRONTIER_AB_NAV_SCENARIO — A→B 無先驗地圖導航場景

> 用途：Paper-2 validity layer 的 **downstream demo 場景定義**（國科會 demo）。
> frontier/exploration **不是貢獻**，只是讓 validity 對「真實導航決策」產生可量測影響的載體。
> 本文件是 **場景規格**，不含實作。

---

## 1. 場景名稱

**Unknown Parking-Lot / Warehouse A-to-B Navigation**（無先驗地圖、線上建圖 + frontier 探索 + 動態物體）。

## 2. 任務定義

- **A（起點）**：robot spawn 位置，定義為 `start_frame`（= odom 原點，t0 對齊）。
- **B（目標）**：在 `start_frame` / `odom` 座標中**座標已知**（例：`(x_B, y_B)`），但 **B 周邊地圖初始未知**。
- **先驗地圖 = 空**（costmap 啟動全 unknown，只有 robot 周邊隨感測逐步 known）。
- robot 必須：online mapping（占據格更新）→ frontier 探索找通道 → 規劃到 B → 抵達。

> 與 GPS-denied 對齊：B 用 **odom/VIO frame** 給定，不依賴全域定位；這正是 Paper-2「GPS-Denied Navigation」標題的 demo 落點。

## 3. 成功條件（量化）

| # | 條件 | 判定 |
|---|---|---|
| S1 | B 被探索成 **known free space** | `/map` 中 B cell 從 −1(unknown)→ 0(free) |
| S2 | planner 能規劃到 B | Nav2 對 goal=B 回傳 valid path（非 `PLANNING` fail） |
| S3 | robot 抵達 B **半徑 0.5 m 內** | `‖odom_xy − B_xy‖ ≤ 0.5 m` 並停穩 |
| FAIL | 撞牆 / 超時 / planner 永久 blocked | 任一觸發即該 trial 失敗 |

預設超時：`T_max = 300 s`（依場景大小可調，須對三組 baseline 一致）。

## 4. 場景元素（必含）

| 元素 | 角色 | 對 validity 的意義 |
|---|---|---|
| **牆（外圍 + 隔間）** | 定義可行通道、製造 unknown | 靜態，frontier 探索主結構 |
| **停放車輛 / 箱子（靜態障礙）** | 製造死路與繞行 | validity 應判 `position_only`（靜止 → 速度不可信）；測試「不要對靜止物做速度預測」 |
| **死路（dead-end）** | 強迫 replan / frontier 放棄 | 測 replan count、planner blocked |
| **狹窄通道（≈1.0–1.2 robot 寬）** | 高風險通行 | validity=warning/unobservable 時應降速/保守 |
| **1–2 個動態行人 / 移動物體** | 真正的動態 | 核心：`full_state`(可信速度→預測) vs `invalid_velocity`(不可信→加 inflation) 的行為差異 |

### 動態物體腳本（建議 2 個）
- **D1 橫越行人**：等速橫越 robot 預定路徑（速度**可觀測** → 期望 validity≈`full_state`，planner 用短時預測讓行）。
- **D2 退化動態**：與 robot **近似同向同速 / 突然停走 / 出現在低 parallax 區**（速度**不可觀測** → 期望 validity≈`invalid_velocity`/`unobservable`，planner 不做速度預測、加大 inflation、降速）。
  → D2 正是 Paper-2 的賣點場景：**naive baseline 會接受錯誤速度導致誤判讓行/搶行**。

## 5. 地圖/座標規格

- frames：`map`（建圖）、`odom`（連續，= start_frame）、`base_link`。
- B 給定方式：`geometry_msgs/PoseStamped`，`header.frame_id = "odom"`（或 `map`，需與 frontier `/frontier_goal` 一致）。
- 初始 costmap：全 unknown；`StaticLayer` 空；靠 `ObstacleLayer/VoxelLayer`（來自 `/scan` 或 BEV）線上填。

## 6. Trial 矩陣（給評估用）

每組 baseline（A/B/C，見 integration plan）× 場景變體，各跑 **N≥10 trials**（不同動態物體相位 / 起始亂數種子）：

| 變體 | 牆 | 靜態障礙 | 死路 | 窄道 | 動態 |
|---|---|---|---|---|---|
| V0 靜態 sanity | ✓ | ✓ | ✓ | ✓ | ✗ |
| V1 單動態（D1） | ✓ | ✓ | ✓ | ✓ | D1 |
| V2 退化動態（D2）★ | ✓ | ✓ | ✓ | ✓ | D2 |
| V3 雙動態 | ✓ | ✓ | ✓ | ✓ | D1+D2 |

★ V2 是「ours 應該贏」的關鍵變體；V0 是「三組應該都過、用來證明我們沒搞壞 baseline」。

## 7. 紅線對齊

- 場景**不引入新 planner**；用現成 Nav2 + `wavefront_explorer`。
- 動態物體可用 **模擬器 ground-truth 或 scripted**；validity 標籤由 Paper-2 V5 模型產生（不是手刻）。
- 若選定模擬器後**場景一時搭不出完整 5 元素**，允許**降級為靜態子集 + 注入式動態**，並在報告誠實標註「partial scene」，不得宣稱完整 demo。

## 8. 待裁示

1. 模擬器（CARLA / Isaac / Gazebo）— 見 audit §7。
2. 場景物理尺寸與 B 距離（影響 `T_max`）。
3. 動態物體用「模擬器 actor」還是「注入式 fake track」（後者較快，但 demo 觀感較弱）。
