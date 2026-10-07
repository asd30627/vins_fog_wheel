# PAPER2_PHASE2_CARLA_CLOSEDLOOP_DRYRUN — 真實 validity × 真 frontier/Nav2 閉環乾跑

> Phase 2（gate 已解鎖：1.6 + 1.7 皆 PASS）。把 **真實 Paper-2 V5 validity label** 用 csv_replay 餵進**未修改的**真 frontier/Nav2 閉環，量測系統健康度與「真實資料驅動 risk-bus」。
> **嚴正定位：這是 DRY-RUN，不是正式 A→B 導航效能。** ego pose 與 map 是 stub、`/scan` 是從物件 GT 合成、Nav2 未給 goal。正式 A→B 數字仍待真 CARLA ego 軌跡 + 真 map + goal。
> **紅線守住**：未改 wavefront_frontier 核心 / Nav2 planner / VINS；無 live detector（csv_replay 真實 label）；未為 ours 調 planner/adapter。

---

## 1. 真實資料來源（非 synthetic）
- 來源：`paper2_v5_object_validity_dataset.csv`（CARLA，15811 列，含 V5 binary validity label）。
- 轉換器：`scripts/paper2_v5_to_replay_csv.py` → 選一個連續 run（**Town10HD / dense / dense_b1**，400 frames），由 binary 欄位還原 5-class、由 `range_m+bearing_deg` 還原位置、`raw_speed_ms` 還原速度。
- 產出：`outputs/phase2/carla_replay_validity.csv`（1726 列 / 400 frames）。
- **真實 class 分布**：unobservable 1185、position_only 370、conservative_warning 75、full_state 90、invalid_velocity 6 → 印證 V5「**多數物件速度不可觀測**」，非我們捏造。

## 2. 閉環接線（全現成 + 新合成 scan）
```
minimal_source(publish_scan=false) → /map /odom /tf        [ego/map = STUB]
validity_publisher(mode=csv_replay) → /object_validity      [REAL V5 labels, 5Hz]
object_scan_synth(/object_validity) → /scan                 [SYNTHETIC, 10Hz]
validity_to_nav_adapter → /paper2/* + /path_cost_monitor/high_cost
        ↓
[未改的真 frontier/Nav2: full_system.launch.py]
```
launch：`paper2_carla_replay_demo.launch.py`；一鍵：`scripts/run_phase2_carla_dryrun.sh`。

## 3. 結果（`outputs/phase2/dryrun_graph.txt`、`dryrun_behavior.csv`；35s）

### 3.1 系統健康
| 檢查 | 結果 |
|---|---|
| 全節點起來 | ✅ minimal_source / object_scan_synth / validity_publisher / validity_to_nav_adapter + 完整 frontier/Nav2 都在 node list |
| 結束無 crash | ✅ 35s 後核心節點（wavefront_frontier / validity_publisher / object_scan_synth / planner_server）全存活 |
| csv_replay 載入 | ✅ `mode=csv_replay rows=1726 frames=400` |

### 3.2 實際資料流（`ros2 topic hz`）
| topic | 速率 | 狀態 |
|---|---|---|
| `/odom` | 29.998 Hz | ✅ |
| `/scan`（合成） | 10.000 Hz | ✅ |
| `/object_validity`（真實 label） | 5.000 Hz | ✅ |
| `/path_cost_monitor/high_cost` | 4.999 Hz | ✅ |
| `/cmd_vel_2` | 29.999 Hz | ✅ |
| `/map` | hz 探針 miss | ⚠️ latched(TRANSIENT_LOCAL) QoS，hz 預設 reliable 訂閱抓不到；但 Nav2 global_costmap 正常消費 + 獨立測試 publisher=1 |
| `/paper2/frontier_risk_cost` | hz 探針 miss | ⚠️ 探針 discovery race；同次 echo 取得 **0.9**、獨立測試 publisher=1 |

> 獨立 bridge-only 測試（乾淨 domain）：`/map /odom /scan /object_validity /paper2/frontier_risk_cost /path_cost_monitor/high_cost` publisher **全 = 1**、`/scan` range_max 30 合成正常 → 證實上面兩個「miss」是**探針/QoS 假象**，非節點故障。

### 3.3 真實資料驅動 risk-bus
- `/object_validity` 樣本（真實）：多為 `unobservable`（velocity 歸零、velocity_valid=false），偶有 `full_state`（帶真實速度 e.g. `[4.345,-2.386]`）。
- `/paper2/frontier_risk_cost` = **0.9**（unobservable-heavy 真實資料 → 高 risk）。
- high_cost：5s 內 **17 True / 5 False**；全程 `high_cost_true=374`。
- risk_behavior_logger：`stopped_on_risk=2238`、**`moved_on_risk=0`**、`stopped_when_safe=126`。

## 4. 判讀（誠實）
- ✅ **真實 Paper-2 validity 能無痛流經整個未改的真 frontier/Nav2 閉環**，35s 無 crash，risk-bus 由**真實資料**驅動（374 次 high_cost，全來自真實 unobservable 物件）。
- ⚠️ `moved_when_safe=0`：閉環中 Nav2 **未給 goal** → `/cmd_vel`≈0 → 機器人本就不動，故此處無法展示「safe 時前進、risk 時停」的對比。**risk→停車的因果已在 Phase 1.6 用注入 `/cmd_vel` 乾淨證明**（stopped_on_risk=240, moved_on_risk=0）；本閉環補充的是「**真實資料**確實產生 risk 訊號並進入真 stack」。
- `moved_on_risk=0` 仍成立：真實 high_cost 期間 `/cmd_vel_2` 從未動 → 與安全語義一致。

## 5. 重現
```bash
source /opt/ros/jazzy/setup.bash && source ~/nav2_ws/install/setup.bash
# 1) 真實 V5 label → replay CSV
python3 ~/nav2_ws/src/paper2_validity_bridge/scripts/paper2_v5_to_replay_csv.py
# 2) 閉環乾跑（真 frontier/Nav2 + 真實 validity）
bash ~/nav2_ws/src/paper2_validity_bridge/scripts/run_phase2_carla_dryrun.sh
cat ~/fwvio_estimator_ws_wheel/outputs/phase2/dryrun_graph.txt
# 只跑 bridge 側：
ros2 launch paper2_validity_bridge paper2_carla_replay_demo.launch.py
```

## 6. 缺口 / 待辦（誠實，距「正式 A→B」還差）
| # | 缺口 | 補法 |
|---|---|---|
| 1 | ego pose = stub（minimal_source 原點靜止） | 接 CARLA 預錄 → VINS odom（`carla_dataset_replay_ros2.py` 已備） |
| 2 | map = stub free-space | 由 CARLA 場景離線生 map 或讓 SLAM 線上建 |
| 3 | `/scan` 為物件 GT 合成（非真 lidar） | CARLA 無 lidar，維持合成或補感測；報告須標「synthetic sensing」 |
| 4 | Nav2 未給 goal → 無真實移動 | 設 A→B goal + 啟用 controller，量 success/time/path/collision（eval protocol） |
| 5 | 單 run（Town10HD dense_b1） | 多 run/town + 多 seed 重複 + 統計 |
| 6 | csv_replay round-robin 非真時間軸 | 對齊真實 frame 時戳與 ego 時鐘 |

→ **本 dry-run 已達成 Phase 2 預定範疇（接線可行性 + 閉環健康 + 真實資料驅動）**；正式 A→B 導航效能屬下一步，且須在補齊 #1/#2/#4 後才可列為主結果。
