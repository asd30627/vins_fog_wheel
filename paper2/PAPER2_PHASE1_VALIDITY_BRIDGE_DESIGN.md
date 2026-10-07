# PAPER2_PHASE1_VALIDITY_BRIDGE_DESIGN — paper2_validity_bridge（skeleton）

> Phase 1 交付：**最小可閉環 Paper-2 downstream demo skeleton**，不依賴 simulator 即可跑起來並用 `ros2 topic echo` 看出 D1/D2 行為差異。
> 紅線全守：未改 `wavefront_frontier.py` 核心、未改 Nav2 planner source、未碰 VINS、無 live detector/tracker、未為 ours 單獨調 planner 參數。

---

## 1. 套件位置與組成
- 路徑：`~/nav2_ws/src/paper2_validity_bridge/`（ament_python，與 frontier 同一 colcon ws，Jazzy）。
- 節點：
  - `fake_track_publisher`（物件來源，無偵測器）
  - `validity_publisher`（Paper-2 validity 產生器：synthetic / csv_replay）
  - `validity_to_nav_adapter`（唯一含 Paper-2→planner 語意的翻譯層）
- launch：`paper2_validity_demo.launch.py`
- 共用：`validity_schema.py`（5-class 常數 + JSON 記錄 helper）

## 2. 資料流
```
fake_track_publisher ──/object_tracks──► validity_publisher ──/object_validity──► validity_to_nav_adapter
   (D0/D1/D2 GT 運動 + 觀測性 hint)        (5-class 規則/CSV)                         │
                                                                 ├─►/paper2/frontier_risk_cost  (Float32, max risk)
                                                                 ├─►/paper2/validity_debug       (String JSON, 逐物件決策)
                                                                 └─►/path_cost_monitor/high_cost (Bool, 既有 frontier risk-bus)
```

### Skeleton 設計選擇（誠實標註）
- `/object_tracks` `/object_validity` `/paper2/validity_debug` 用 **`std_msgs/String` 載 JSON**，避免 skeleton 階段引入自訂 rosidl msg，且每個 topic 都 `ros2 topic echo` 可讀。
  → **TODO(phase-2)**：遷移到 `vision_msgs/Detection3DArray` 或專用 `ObjectValidity.msg`。
- `validity_publisher` 的 synthetic 規則是**透明幾何 proxy**，不是學習推論；用途是在無 CARLA 下讓 D1/D2 行為可重現。csv_replay 模式已接線（讀 `paper2_v5_build_validity_labels.py` 風格 CSV），等真資料即可換上。

## 3. 物件來源：fake_track_publisher
| track | 設定 | 觀測性 hint |
|---|---|---|
| **D0 static** | 4m 前方靜止箱/車，speed=0 | parallax 高、無速度 |
| **D1 crossing** | 等速橫越（sawtooth wrap，速度不過零），speed=1.2 | bearing_change=0.9、parallax=0.7 → **速度可觀測** |
| **D2 degenerate** | 每 `d2_mode_period_s` 輪換 3 模式 | 皆「速度不可信」 |
| └ same_speed | 與 ego 同向同速 | bearing_change=0.05（低相對資訊） |
| └ low_parallax | 遠(28m)、低 parallax、高 depth jitter | parallax=0.12, jitter=0.7 |
| └ sudden_stop | 速度 0/1.5 突變 | 破壞等速模型 |

參數：`enabled_tracks`（`all` 或 `D0,D1,D2` 子集，供隔離測試）、`rate_hz`、`d2_mode_period_s`。

## 4. validity 規則（validity_publisher synthetic，閾值可 ablation）
依序判斷（鏡像 V5 label 意圖）：
1. `speed < speed_static(0.15)` → **position_only**（位置可信、速度無意義）
2. `parallax < 0.20` 或 `range > 25` 或 `depth_jitter > 0.5` → **unobservable**（速度結構不可觀測）
3. `bearing_change_rate < 0.15` → **invalid_velocity**（同向同速/突停）
4. 邊界信心帶 → **conservative_warning**
5. 其餘（清楚橫向運動＋好 parallax）→ **full_state**（唯一 `velocity_valid=True`）

## 5. Adapter 翻譯策略（validity_to_nav_adapter）
| class | velocity prediction | risk | inflation | high_cost |
|---|---|---|---|---|
| full_state | **允許**（horizon=`tau`，預設1.0s） | 0.0 | base | 否 |
| position_only | 否（只用當前位置） | 0.1 | base | 否 |
| invalid_velocity | **禁止** | 0.6 | enlarged | 否（除非 `near_high_cost_range` 內，預設關） |
| conservative_warning | 否 | 0.6 | base | 否 |
| unobservable | 否 | 0.9 | enlarged | **是**（≥`high_cost_threshold` 0.8） |

- `/paper2/frontier_risk_cost` = 全物件 risk 最大值。
- `/path_cost_monitor/high_cost` = 任一物件 risk≥threshold → True（unobservable 觸發；invalid_velocity 只抬 risk，不 high_cost，符合「risk 或 high_cost」）。
- 參數：`high_cost_threshold`、`near_high_cost_range`、`publish_high_cost`、`velocity_prediction_horizon_s`。

## 6. 驗證結果（實測，2026-06-30）
獨立啟動（無 simulator），實測：

| 成功條件 | 觀測 | 結果 |
|---|---|---|
| bridge 不靠 sim 自己跑起來 | launch 三節點齊起 | ✅ |
| **D1 full_state 不亂觸發 high_cost** | D1-only：high_cost 串流全 `False`、risk=0、`velocity_prediction:true, horizon:1.0` | ✅ |
| **D2 invalid_velocity/unobservable 觸發 risk/high_cost** | D2-only：出現 `high_cost:true`、`validity_class:unobservable, risk:0.9, escalated:true`；same_speed 相位則 `invalid_velocity, risk:0.6` | ✅ |
| **static 不做 velocity prediction** | D0：`position_only, velocity:[0,0,0], velocity_prediction:false` | ✅ |

`/object_validity` 實測樣本（all-tracks）：
```json
{"objects":[
 {"id":0,"validity_class":"position_only","velocity":[0,0,0],"velocity_valid":false,"source_type":"D0"},
 {"id":1,"validity_class":"full_state","velocity":[0,1.2,0],"velocity_valid":true,"source_type":"D1"},
 {"id":2,"validity_class":"invalid_velocity","velocity":[0,0,0],"velocity_valid":false,"source_type":"D2"}]}
```

## 7. 與 frontier 的接合（未來，非本次改動）
- adapter 已 publish 既有 `/path_cost_monitor/high_cost`（G5 證實 sub=twist_servo+goal_repeater）→ 同時跑 frontier 時**自動驅動安全停/換點**，零改 frontier。
- `dynamic_obstacle_layer` / `SpeedFilter` 注入留待後續（改 Nav2 param yaml，不改 planner code）。

## 8. 已知限制（誠實）
- synthetic validity 是幾何 proxy，非學習模型；數字非真實 CARLA 結果（csv_replay 待接真資料）。
- String/JSON topic 是 skeleton 權宜，未來換 typed msg。
- 尚未接真 frontier 閉環與 A→B（需資料源，見 G5 文件）。
- baseline A/B（always-full / distance-gate）尚未實作（下一步：在 validity_publisher 加 `policy` 參數切換來源，planner/adapter 不動，確保公平）。
