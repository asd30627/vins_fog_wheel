# PAPER2_PHASE1_G5_FRONTIER_SMOKE_TEST — 原版 frontier/Nav2 啟動驗證

> 目的：證明既有 `wavefront_explorer` + Nav2 在 `~/nav2_ws` 能起來、lifecycle 啟用、risk-bus 與 get_costmap service 在線。
> **未改任何 code。**

## 1. 方法
- workspace：`~/nav2_ws`（已 build）。
- 指令：`ros2 launch wavefront_explorer full_system.launch.py`（含 `multi_tools` glue + Nav2 `navigation_launch` + rviz）。
- 等 45s 讓 lifecycle 自動 activate，再快照 `ros2 node/topic/service list` + key topic info，然後整組 teardown。
- log：`scratchpad/g5_launch.log`、`scratchpad/g5_graph.txt`。

## 2. 結果：✅ Graph 起得來且 lifecycle-active

**Active nodes（31 個，節錄）**：
`wavefront_frontier`、`goal_repeater`、`odom_bridge`、`path_cost_monitor_node`、`twist_servo`、`scan_fix_node`
＋ Nav2：`bt_navigator`、`planner_server`、`controller_server`、`behavior_server`、`smoother_server`、`velocity_smoother`、`collision_monitor`、`waypoint_follower`、`route_server`、`docking_server`、`global_costmap/global_costmap`、`local_costmap/local_costmap`、`lifecycle_manager_navigation`、`rviz`。

**關鍵 service / topic 在線**：
| 檢查項 | 結果 |
|---|---|
| `/global_costmap/get_costmap` service | ✅ 存在（count=1）→ `wavefront_frontier` 啟動時的 blocking wait 被滿足 |
| `/global_costmap/costmap_raw` | ✅ pub=1, sub=4 |
| `/path_cost_monitor/high_cost` | ✅ **pub=2, sub=2**（risk-bus 真的接著 `twist_servo` + `goal_repeater`） |
| `/path_cost_monitor/enable` | ✅ pub=1, sub=1 |
| `/cmd_vel → /cmd_vel_2` | ✅ `/cmd_vel` pub=2/sub=1，`/cmd_vel_2` pub=1（twist_servo 安全閘輸出；底盤端無 sub＝模擬/實機未接，預期） |
| `/frontier_goal` `/frontier_goal_repeat` | ✅ 皆在線 |
| lifecycle_manager_navigation `manage_nodes` | ✅ 在（autostart 生效） |
| idle 時 `high_cost` echo | timeout（無訊息）→ 靜止基線＝不亂觸發，正確 |

## 3. ⚠️ 誠實缺口：Graph「起得來但餓著」（confirm audit G3/G5）

| Topic | Publisher count | 意義 |
|---|---|---|
| `/map` | **0** | 沒有建圖來源在這條 launch（SLAM/AMCL/rtabmap 皆未啟，rtabmap 被註解） |
| `/odom` | **0** | 沒有里程計來源（待接 VIO/輪速/sim） |
| `/scan` | **0** | 沒有雷射/感測來源 |

→ 結論：**frontier+Nav2 的「軟體骨架」完全可起、可 lifecycle-active、risk-bus 與 costmap service 都在**；但**缺 `/map` `/odom` `/scan` 的資料產生者**，所以**現在還無法真正 A→B 導航**。這正是 Phase 0 audit 預期的 G3（資料來源不在 frontier launch 內）與 G5。**不是 frontier 壞了，是缺一個 sensor/localization/sim 來源。**

## 4. 對 Phase 1 的意義
- ✅ **risk-bus 可用**：`/path_cost_monitor/high_cost` 有真實 subscriber（twist_servo 安全停 / goal_repeater 換點）。我們的 `validity_to_nav_adapter` publish 這條時**會真的驅動行為**，不需改 frontier。
- ✅ **adapter 不依賴 sim**：bridge 可獨立驗證（見 design 文件），與 frontier 是否有資料源解耦。
- 待補（後續 Phase）：A→B 真閉環需要補一個資料源（sim / bag / VIO odom）餵 `/map` `/odom` `/scan`。**這是場景端工作，非 planner 工作。**

## 5. 重現指令
```bash
source /opt/ros/jazzy/setup.bash
source ~/nav2_ws/install/setup.bash
export ROS_DOMAIN_ID=68
ros2 launch wavefront_explorer full_system.launch.py
# 另一個 terminal：
ros2 node list
ros2 service list | grep get_costmap
ros2 topic info /path_cost_monitor/high_cost
ros2 topic info /map      # Publisher count: 0  ← 待接資料源
```
