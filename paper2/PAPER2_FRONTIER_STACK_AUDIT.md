# PAPER2_FRONTIER_STACK_AUDIT — Phase 0 環境稽核

> 角色定位：frontier 只是 **downstream validation / 國科會 demo**，不是 Paper-2 主貢獻。
> Paper-2 主題不變：**Temporal-Consistency-Aware Selective Object State Validity for GPS-Denied Navigation**。
> 本文件只做「現況稽核」，不改 code。

---

## 0. TL;DR（誠實版）

- **不是 Docker。** 目前 Docker 只有 Overleaf/LaTeX 容器（`sharelatex / git-bridge / redis / mongo`），**沒有任何 frontier / nav container**。
  → 你問題裡「Docker 裡現有的 frontier stack」這個前提**不成立**，frontier 是 **host native ROS 2** 跑的。
- **ROS 版本：ROS 2 Jazzy**（`ROS_DISTRO=jazzy`, `/opt/ros/jazzy`），不是 ROS1。
- **Frontier package = `wavefront_explorer`**（自寫 wavefront frontier + 一堆 glue node），底層用 **Nav2** 當 planner、**rtabmap**（目前在 launch 中被註解掉）當建圖選項。
- **可跑的 workspace = `~/nav2_ws`**（已 build，有 `install/`）。`~/nstc_autonav_ws` 的 `src/` 與 nav2_ws **完全相同**（`wavefront_frontier.py` diff 為空），但 **沒 build（無 install/）**。`~/rgbd_ws` 是另一份較舊/精簡版。
- **三個紅線相關的硬缺口（後面詳列）**：
  1. **沒有 live `/object_validity` topic** — Paper-2 V5 validity 全是 **offline Python 腳本**（CARLA Town10HD+Town01 bag 上跑），**沒有任何 rclpy/rclcpp ROS node**。
  2. **沒有現成的 A→B parking-lot 模擬場景** — `my_robot_bringup` 裡只有一個 BT xml，**沒有 world / launch / robot model**；資料來源（/scan、/map、/odom 誰產生）在 launch 裡看不出來（rtabmap 被註解、無 gazebo world、有 Isaac `AMR.usd` 與 `isaac_nav2_params.yaml` 殘跡但無啟動腳本）。
  3. **frontier stack 目前能不能一鍵跑起來＝未驗證**（見 §6 風險）。

---

## 1. Container / Runtime 判定

| 項目 | 結果 |
|---|---|
| Docker frontier container | ❌ 無（只有 overleaf 那組） |
| ROS 版本 | **ROS 2 Jazzy**（native，非容器） |
| `ros2` CLI | `/opt/ros/jazzy/bin/ros2` ✅ |
| `roscore`（ROS1） | ❌ 無 |
| `ROS_DOMAIN_ID` | 68 |
| RMW | 預設（fastdds，workspace 內有 `fastdds_udp.xml`） |

**結論：以 native ROS 2 Jazzy 為整合目標，不要假設 Docker。**

---

## 2. Workspace / Package 盤點

| Workspace | 是否 build | wavefront_explorer | 備註 |
|---|---|---|---|
| `~/nav2_ws` | ✅ 有 `install/` | ✅ | **建議當作 runnable baseline** |
| `~/nstc_autonav_ws` | ❌ 無 install | ✅（src 同 nav2_ws） | 國科會命名，但未 build |
| `~/rgbd_ws` | ✅ 有 install | ✅ + `amr_simple_control` | 較舊/精簡 |

Frontier package：`wavefront_explorer`
- launch：`wavefront_frontier.launch.py`、`full_system.launch.py`、`multi_tools.launch.py`
- 主要 node（`setup.py` console_scripts）：
  `wavefront_frontier`（核心）、`goal_repeater`、`scan_fix_node`、`odom_bridge`、`path_cost_monitor_node`、`twist_servo`、`bev_pcl`、`bev_sem2d_to_scan`、`camera_mux`、`sixcam_preprocess`、`publish_camera_optical_tf`。

**啟動鏈**：`full_system.launch.py` → include `multi_tools.launch.py`（起 scan_fix / odom_bridge / twist_servo / goal_repeater / path_cost_monitor / wavefront_frontier）＋ Nav2 `navigation_launch.py`＋ Nav2 `rviz_launch.py`。rtabmap include **被註解掉**。

---

## 3. Topic / 介面圖（實測自 source）

### 3.1 Map / Occupancy
| Topic | 型別 | 方向 | 來源 node |
|---|---|---|---|
| `/map` | `nav_msgs/OccupancyGrid` | sub | `wavefront_frontier`（frontier 偵測） |
| `/global_costmap/costmap_raw` | `nav2_msgs/Costmap` | sub | `wavefront_frontier`、`path_cost_monitor_node` |
| `/global_costmap/get_costmap` | `nav2_msgs/srv/GetCostmap` | client | `wavefront_frontier`（啟動時等此 service） |

### 3.2 Odom
| Topic | 型別 | 方向 | node |
|---|---|---|---|
| `/odom` | `nav_msgs/Odometry` | in | 系統輸入（產生者未在 frontier 內，見 §6） |
| `/odom_nav2wfd` | `nav_msgs/Odometry` | `odom_bridge` 轉發（TRANSIENT_LOCAL） | frontier 透過 remap `/odom→/odom_nav2wfd` 吃 |

> **Paper-1 / VINS 對接點**：`/odom` 就是定位輸出口。GPS-denied 時這裡換成 VIO/VINS odom 即可，**不需要碰 VINS backend**。

### 3.3 Scan / Pointcloud
| Topic | 型別 | node |
|---|---|---|
| `/scan`（fix 後） | `sensor_msgs/LaserScan` | `scan_fix_node`（in→修正→out） |
| BEV→scan | `sensor_msgs/LaserScan` | `bev_sem2d_to_scan`（語意 BEV 轉假雷射） |
| BEV pcl | `sensor_msgs/PointCloud2` | `bev_pcl`（occ3d→raw/inflated cloud） |

### 3.4 Goal
| Topic | 型別 | 流向 |
|---|---|---|
| `/frontier_goal` | `geometry_msgs/PoseStamped` | in → `goal_repeater` |
| `/frontier_goal_repeat` | `geometry_msgs/PoseStamped` | `goal_repeater` → `wavefront_frontier`（final goal bias） |
| `follow_waypoints` | `nav2_msgs/action/FollowWaypoints` | `wavefront_frontier` → Nav2（實際導航） |
| `initialpose` | `geometry_msgs/PoseWithCovarianceStamped` | `wavefront_frontier` → Nav2 AMCL/初始化 |

### 3.5 Cmd_vel（含安全閘）
| Topic | 型別 | 流向 |
|---|---|---|
| `/cmd_vel` | `geometry_msgs/Twist` | Nav2 controller → `twist_servo` |
| `/cmd_vel_2` | `geometry_msgs/Twist` | `twist_servo` → 底盤（**經安全停車閘**） |

### 3.6 Costmap / Planner / 既有「risk bus」★
| Topic | 型別 | 角色 |
|---|---|---|
| `/path_cost_monitor/enable` | `std_msgs/Bool` | frontier → monitor 開關 |
| `/path_cost_monitor/high_cost` | `std_msgs/Bool` | monitor → `twist_servo`(安全停)＋`goal_repeater`(換點) |
| `/goal_repeater/blocked` | `std_msgs/Bool` | goal_repeater 狀態 |
| `/plan`（path_topic 參數） | `nav_msgs/Path` | monitor 取 planner path 採樣成本 |

> ★ **這條既有的 `high_cost` / `blocked` risk bus 是 Paper-2 validity 注入的最自然落點**：系統已經有「收到 Bool → 安全停 / 換 frontier 點」的行為，我們的 validity 只要餵這條匯流排或新增平行的 risk topic，就能影響行為而**不改 planner 核心**。

---

## 4. Planner 堆疊

- **Global/Local planner = Nav2**（`nav2_bringup/navigation_launch.py`），costmap = `global_costmap` / `local_costmap`。
- 可用 costmap 層（src 內出現過的 plugin）：`StaticLayer`、`ObstacleLayer`、`VoxelLayer`、`InflationLayer`、`KeepoutFilter`、`SpeedFilter`。
  → **`KeepoutFilter` / `SpeedFilter`（costmap_filters）= 不改 planner 就能注入 mask/限速的官方機制**，是 adapter 的乾淨選項之一。
- Behavior Tree：`my_robot_bringup/bt/my_hybrid_nav.xml`（hybrid nav BT，存在但未確認被誰載入）。

---

## 5. Paper-2 validity 現況（對接面）

- Paper-2 V5「selective validity + refusal」目前是 **offline**：`scripts/paper2_v5_*.py`、`paper2_train_selective_validity.py`，在 CARLA bag 上算 label / OVI / refusal policy。
- **沒有任何 ROS node**會 publish validity。5 類輸出（`full_state / position_only / invalid_velocity / unobservable / conservative_warning`）目前只存在於 CSV / 報告。
- 對接 frontier ⇒ **必須新寫一個小 publisher node**（inference 或 replay），這算 Phase 1 的「minimal integration」，**不是改 frontier**。

---

## 6. 硬缺口 / 風險（誠實列，不硬包裝）

| # | 缺口 | 影響 | Phase 1 需補 |
|---|---|---|---|
| G1 | 無 live `/object_validity` publisher | adapter 沒輸入 | 寫 1 個 replay/inference node（讀 V5 CSV 或 model → 發 `vision_msgs`/自訂 msg） |
| G2 | 無 A→B parking-lot 場景 / world / robot model | demo 跑不起來 | 需決定模擬器（見 §7）並建場景 |
| G3 | `/odom`、`/map`、`/scan` 產生者不在 frontier launch 內 | 不確定誰建圖、誰定位 | 釐清：是 Nav2 SLAM？rtabmap（被註解）？外部 bag？ |
| G4 | `nstc_autonav_ws` 未 build | 國科會命名 ws 不能直接跑 | 用 `nav2_ws` 或重 build nstc |
| G5 | 整體 `full_system.launch.py` 未實測能起來 | demo 可行性未證 | Phase 1 第一步＝先讓原版 frontier 在某場景能 A→B（baseline 不含 Paper-2） |
| G6 | 物件偵測→追蹤 live pipeline 未確認 | validity 的「物件」哪來？ | demo 可先用 **scripted/sim ground-truth 物件**，validity 用 V5 模型分類；live 偵測列為 stretch |

> **判斷**：缺口集中在「**輸入端**（validity publisher、物件來源）」與「**場景端**（模擬器/world）」，**frontier 本體與 Nav2 是現成的**。這對「downstream validation demo」是好消息——主要工作是接線與造場景，不是重寫 planner。

---

## 7. 模擬器選項（待你裁示，Phase 1 才動）

| 選項 | 證據 | 優點 | 缺點 |
|---|---|---|---|
| **CARLA** | Paper-2 全部資料都在 CARLA；workspace 有 `CARLA_*` 報告 | validity 模型同源、物件 GT 現成 | 停車場/倉庫場景要搭、CARLA↔Nav2 bridge 要接 |
| **Isaac Sim** | `AMR.usd`、`isaac_nav2_params.yaml` 殘跡 | 室內 AMR 場景天然、Nav2 整合成熟 | validity 模型非此域、要重採物件 |
| **Gazebo** | rtabmap demo 多為 gazebo/turtlebot | 輕、A→B demo 經典 | 與 Paper-2 物件域差最遠 |
| **純 bag replay** | 最省 | 不用模擬器 | 無法「導航到 B」閉環，只能離線重放 → demo 力道弱 |

**建議（待裁示）**：國科會 demo 重點是「validity 影響導航行為」的閉環，CARLA 與 Paper-2 同源最一致；若要室內停車場 AMR 觀感，Isaac 較像。**先別決定**，等你 §場景 拍板。

---

## 8. 一句話結論

> frontier stack = **native ROS 2 Jazzy + `wavefront_explorer` + Nav2**，可跑於 `~/nav2_ws`；**現成、可注入**（已有 risk-bus 與 costmap_filter 機制），但**輸入端（live validity publisher、物件來源）與場景端（A→B world）目前是空的**，這兩塊是 Phase 1 的真正工作量。**沒有需要改 planner、改 VINS、加 object factor 的地方。**
