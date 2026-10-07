# Shared Object Persistence Memory for Coupled ORB-SLAM3 Backend and Prior-Map-Free Frontier Navigation — v3

> 主軸（不變）：Shared object persistence memory for coupled ORB-SLAM3 backend and prior-map-free frontier navigation.
> 核心不是 object detection/tracking 本身，而是 per-object persistence/anchor belief 進入 ORB-SLAM3 backend，同一層 candidate-anchor/static support 被 frontier planner 用來估 localization risk，並以 closed-loop CARLA + offline KITTI Tracking 驗證。

**版本說明**：專案裡（`fwvio_estimator_ws_wheel` 及相關 `~/orbslam_ws`、`~/nav2_ws`、`~/nstc_autonav_ws`、`~/fwvio_ws`、`~/vins_ws`）**找不到 `openspec_shared_object_memory_orbslam_frontier_v2.md`**，也找不到任何早期 v1 版本檔案。本 v3 是直接依當前 repo 稽核事實從頭撰寫，並非在既有 v2 文字上增補——若使用者手邊另有 v2 原稿（例如來自其他工具/對話），需要提供後才能做逐段差異合併；目前內容以「這條方向若要啟動，現況基礎在哪裡、缺口在哪裡」為準。

---

## 0. 使用前必讀：與現有專案方向的衝突（未經裁示，不建議直接啟動）

稽核中發現兩個需要使用者明確裁示的衝突點，先列在最前面，不藏在文末：

1. **PI 稽核方向（同日 2026-07-02）已裁示**：Paper-2 目前唯一 paper-ready 的線是 KITTI Mondrian OPL；下一步是「寫 OPL 論文」，且明確「禁開新 branch」。本文件描述的 ORB-SLAM3 backend + object persistence + frontier coupling 是一條全新研究線，目前不在 `openspec/changes/` 任何已核准 change 內（現有 changes：`dynamic-object-validity-routing`、`grade-conditioned-inertial-fusion`、`navigation-integrity-monitoring`、`paper2-noue-g0-data-grounding`、`paper2-observability-aware-object-validity-v5`、`paper2-viwo-conditioned-noue-v4`、`route-c-motion-conditioned-aniso-cov`）。
2. **既有 frontier 紅線（Phase 0/1 稽核，2026-06-30）**：frontier 是 downstream demo，不是主貢獻；不改 planner、不碰 VINS backend、不加 object factor、不宣稱新 frontier planner。本文件第 4、6、7 節描述的「P1 backend candidate-anchor / P2 planner coupling gain」若真的實作，會直接觸碰這條紅線（是 backend 的 ORB-SLAM3，不是 VINS，但仍是「改 SLAM backend + 改 planner 消費方式」的範疇，需要重新裁示是否例外）。

本文件僅為**稽核 + 規劃**產出，未動任何程式碼、未開新 branch、未跑新實驗。是否進入 Phase 1 實作，等待使用者裁示。

---

## 1. Purpose / Research Positioning

- 目標：驗證「ORB-SLAM3 backend 產生的 per-object anchor belief（哪些物體是可靠的靜態/半靜態地標）」是否能同時：(a) 降低 backend 自身被動態物體污染 BoW/local BA 的風險；(b) 提供 frontier planner 一個比「純幾何 occupancy」更細緻的 localization-risk 訊號。
- 明確**不是**：不是新的 detection/tracking 演算法研究、不是新的 frontier planner 演算法研究、不是要取代 VINS-Fusion（本 repo 主估計器與本方向完全獨立，見附錄 Topic A）。
- 定位：屬於 Paper-2 生態圈內「若獲裁示」的延伸/備用方向，非目前已核准主線。

## 2. v1 Sensor Scope：Stereo-Only

- **現況與此假設有落差**：ORB-SLAM3 wrapper（`~/orbslam_ws/src/orb-slam3-ros2/`）已建置 `mono/stereo/rgbd/rgbd-inertial/stereo-inertial` 五種模式，**KITTI 用純 `stereo`（無 IMU）**，**CARLA/EuRoC 用 `stereo-inertial`**（見附錄 Topic A）。也就是說「stereo-only」目前只在 KITTI 端成立，CARLA 端實務上已經是 stereo-inertial。
- 若 v1 堅持「stereo-only，不耦合 IMU」，需要明確決定：CARLA 側是否要新增一條 stereo-only（無 IMU）跑法作為 v1 對照組，否則現有 CARLA 結果（如 `PHASE6_ORBSLAM3_VS_VINS_CARLA_REPORT.md` 的 2.06 m vs 41.69 m ATE）是 stereo-inertial 而非 stereo-only，不能直接當 v1 baseline 引用。

## 3. Three Contributions（沿用原始骨架，因無 v2 可比對差異）

1. Per-object persistence / anchor belief 進入 ORB-SLAM3 backend（決定哪些偵測物是可信賴的地標候選）。
2. 同一層 candidate-anchor / static support 被 frontier planner 用來估計 localization risk（非 occupancy risk）。
3. Closed-loop CARLA + offline KITTI Tracking 雙軌驗證。

## 4. Required Architecture

現況落差（決定架構起點）：

- **ORB-SLAM3 wrapper 目前完全沒有 live MapPoint/KeyFrame ROS 介面**——grep 遍尋 `create_publisher`/`PointCloud`/`MapPoint` 在 wrapper 節點內皆無結果；唯一輸出是 (a) 逐幀 camera pose 透過自訂 `ORBSLAM_TRAJ_TUM` 環境變數寫 TUM 檔案（今日 2026-07-02 剛加，未 commit），(b) shutdown 時一次性 `SaveKeyFrameTrajectoryTUM`。**這是本方向最大的單一缺口**：任何「per-object anchor belief 進 backend」都需要先有 per-keyframe MapPoint-observation-with-track-id 的即時輸出，這個能力目前是 0，不是「弱」，是「無」。
- ORB-SLAM3 核心（`orbslam3_core/`）是 vendored 原始碼（非 git submodule），只有 wrapper 層節點檔案被證實客製化過；backend 修改若發生，範圍應嚴格限制在 wrapper 層新增 publisher，不動 `orbslam3_core` 內的 BA/Optimizer 邏輯。
- Frontier 側最接近的既有骨架是 `nav2_ws/src/paper2_validity_bridge/`（`validity_publisher_node.py`、`validity_to_nav_adapter.py`、`risk_behavior_logger_node.py` 等，已建置可跑）——但這是「風險匯流排（risk bus）」，發布 `/path_cost_monitor/high_cost`，**不是**持久化的 object-anchor store。若要做 candidate-anchor 供 planner 消費，需要在此之上新增一層 anchor 狀態儲存，而非直接重用現有 topic 語意。

## 5. Online Occupancy / Traversability Map Spec

- Nav2 costmap：`nav2_ws/src/navigation2/` 是完整 vendored 上游 clone，**找不到任何專案自訂的 `global_costmap`/`local_costmap` yaml**（只有 `rtabmap_ros` 內未使用的 demo 範例參數），代表目前跑的是 Nav2 stock 預設值，沒有針對本專案調過。
- Frontier：`wavefront_explorer/wavefront_explorer/wavefront_frontier.py` 是真實可跑的 frontier 節點，透過 `nav2_msgs.srv.GetCostmap` 拿 Nav2 costmap，已建置。
- Depth→occupancy 路徑：`bev_sem2d_to_scan.py` 把 BEV semantic 影像轉成合成 `LaserScan`（`/bev/scan`）餵給 Nav2 stock obstacle layer——這不是完整 occupancy grid/`/map` 發布者，是「合成掃描」等級。
- **沒有找到任何自訂 dynamic obstacle cost layer plugin**（grep 自訂 `nav2_costmap_2d::Layer` 子類別為空，只有 stock Nav2 / `rtabmap_costmap_plugins`）。
- 誠實結論：v1 要求的「localization risk 只計算過往 frontier 已知 traversable segment，frontier 前方 unknown region 不因沒有 sparse map points 被懲罰」這條規格，**目前完全沒有對應實作**，且連基礎 occupancy map 都是 stock Nav2 + 合成掃描，非本專案自建。

## 6. Implementation Roadmap Phase 0–5（規劃，未執行）

- **Phase 0（本次，已完成）**：純稽核，產出本文件。
- **Phase 1（未啟動，待裁示）**：ORB-SLAM3 wrapper 新增 per-keyframe MapPoint-with-track-id 即時 publisher（僅新增 topic，不碰 core）；同時解決 shutdown BA hang（見第 11 節）避免每次驗證都要 SIGKILL。
- **Phase 2（未啟動）**：candidate-anchor 分類邏輯（STATIC/CANDIDATE_ANCHOR/UNKNOWN/TRANSIENT_OBJECT）+ demotion 規則，用 CARLA `anchor_recovery_preview`（`dynamic_v3r8`，`npc_static_frac` 停等車情境）驗證。
- **Phase 3（未啟動）**：frontier 消費層——在 `paper2_validity_bridge` 之上新增 candidate-anchor 匯入，透過 Nav2 `KeepoutFilter`/`SpeedFilter` 或既有 risk-bus 注入，不改 planner 本身。
- **Phase 4（未啟動）**：two-sided gate 驗證（見第 11 節條件）。
- **Phase 5（未啟動）**：closed-loop CARLA + offline KITTI 雙軌評估；closed-loop 目前僅有 dry-run 等級基礎（見附錄 Topic E），非正式 A→B。

## 7. Ablation Table

| 代號 | 說明 | 現況 |
|---|---|---|
| B1 | ORB-SLAM3 baseline（無 anchor） | ✅ 現成，`run_orbslam_*` 系列腳本 + `evo_ape` ATE pipeline 已可跑 |
| B3 | all_dynamic / class-prior masking | ✅ 部分現成：`logs/phase6/stereo_mask_dense_all_dynamic.json` 已存在 |
| **B4** | **geometric / optical-flow dynamic mask** | ❌ **完全缺失**——稽核未找到任何 optical-flow 或純幾何動態偵測模組；現有 mask 生成器（`phase6_make_stereo_mask.py`、`paper2_make_vins_masks.py`、`paper2_make_tcsvm_mask.py`、`paper2_make_random_mask.py`）都不是幾何/光流法。這與原稿「B4 是 learned persistence 的主要競爭者，必須先確認 B4 是否已足夠」的前提衝突：現況是 B4 根本不存在，不能跳過直接做 C3。 |
| C3 | culling + candidate anchor recovery | ❌ 未實作 |
| P1 | backend-only candidate-anchor | ❌ 未實作（缺 Phase 1 前提） |
| P2 | planner-only raw object memory | ⚠️ 部分可沿用 `paper2_validity_bridge`，但語意需重新定義（風險匯流排≠raw object memory） |
| P3 | combined P1+P2 | ❌ 未實作 |

## 8. Metrics

- ATE/RPE：✅ 現成，`evo_ape` 已整合進所有 `run_orbslam_*_logged.sh`。
- Loop-closure precision：⚠️ 有一筆可用素材（`Town01__dynamic_v3loop__runlong_fix4`，900 m/248 s，GT loop closure 0.3 m@t=229s），但 **ORB-SLAM3 內部偵測到 loop 後拒絕修正**（`PHASE6_CARLA_LOOP_RECORDING_AND_ORBSLAM3_RESULT.md` 記載 `BAD LOOP!!!`）——這是誠實的負結果，不是「已驗證可用」，做 loop-closure precision metric 前要先排查這個拒絕原因。
- near_collision / min_clearance：✅ 已有先例（`mini_world_sim` 在 Phase 3 AB-NAV 產出過這類 metric），但是繞過 Nav2 用自製 potential-field controller 算的，不是真正 Nav2-in-loop 的數字。
- Coupling gain（`backend_gain = P1-B1`、`planner_gain = P2-B1`、`combined_gain = P3-B1`、`coupling_residual = combined_gain - backend_gain - planner_gain`）：❌ 全新定義，目前無任何資料支撐，需 Phase 1-3 完成後才能算。

## 9. Edge AI Execution Budget

- 本機開發/執行 GPU：`nvidia-smi` 回報 **NVIDIA GeForce RTX 5090**（桌上型，非嵌入式）。
- 全 repo 搜尋 `Jetson`/`Orin`/`GX10` 皆為零命中。**目前完全沒有 edge 硬體目標或量測基礎**。
- 若 v1 規格書仍要保留原稿的 multi-rate budget 表（ORB-SLAM3 15–25Hz、detector 5–10Hz…），必須明確標註「這是規劃值，非本專案任何硬體上實測值」，不可暗示已驗證。

## 10. Label Timing / Async Contract

- 全 repo 只找到**一處** `ApproximateTimeSynchronizer` 使用（`nav2_ws/src/bev_infer/bev_infer/bev_infer.py`），且與 object persistence 無關（是 BEV 推論用）；該檔案內還有約 9 段被註解掉的舊版同步邏輯，顯示曾反覆調整。
- `paper2_validity_bridge`、`wavefront_explorer`、VINS-Fusion 三者**皆未使用** `message_filters`/timestamp 同步——各 topic 各自獨立 rate 發布（已知數字：`/object_validity` 5Hz、合成 `/scan` 10Hz、stub `/odom` ~30Hz、`/path_cost_monitor/high_cost` ~5Hz、`/cmd_vel_2` ~30Hz、VINS reliability logger ~10Hz/keyframe、CARLA IMU 100Hz/影像 20fps）。
- 結論：v1 規格要求的「detector/SLAM keyframe 非同步 + timestamp interpolation + MapPoint ownership 多次 observation voting」這整套 async contract，**目前在任何現有節點裡都沒有先例可循**，是從零開始的工程項目，不是「調整既有機制」。costmap 更新率、frontier replan 週期、local planner 執行率三者也完全沒有文件化數字。

## 11. Risks / Gates

延續既有紅線（見第 0 節）：frontier 非主貢獻、不改 planner、不碰 VINS backend、不加 object factor、不宣稱新 frontier planner。本方向額外風險：

- **方向裁示風險**：本文件描述的方向與 2026-07-02 當天的 PI 裁示（禁開新 branch，聚焦 OPL 論文）沒有對齊，啟動前需要使用者明確再次裁示這是否為授權例外。
- **ORB-SLAM3 穩定性**：wrapper 現有已知問題——shutdown 時 global BA 會 hang，所有既有腳本靠 SIGINT 後 SIGKILL 收尾。任何 backend 新增 publisher 的改動，必須先確認不會讓這個 hang 更難排查。
- **Nav2 batch harness 不穩**：完整 `navigation_launch` 在批次/背景模式下觀察到約 11.5 秒後整組退出（Phase 3 AB-NAV 因此改用自製 controller 繞過 Nav2）；真正 Nav2-in-loop 驗證需要互動式 terminal，非自動化腳本可靠完成，這會影響 Phase 4/5 的可重現性。
- **Two-sided anchor recovery gate 素材**：CARLA 現有錄製涵蓋 low-texture/low-light/visual-outage、停等車（`npc_static_frac`）、密度分級（sparse/medium/dense）、一筆 return-visit/loop 錄製；**完全沒有行人/移動行人穿越場景**（collector 內 grep `walker` 為零命中，只有車輛 NPC），也沒有明確的 stop-and-go 車輛行為旗標。若 gate 條件要求 pedestrian crossing，現有資料集不足，需要新錄製。

## 12. First Three Implementation Tasks（若獲裁示放行才啟動）

1. 在 `orb-slam3-ros2` wrapper（`stereo-slam-node.cpp`/`stereo-inertial-node.cpp`）新增 per-keyframe MapPoint-with-track-id 的最小 ROS topic publisher，範圍限定 wrapper 層，不改 `orbslam3_core`。
2. 建立 B4（geometric/optical-flow dynamic mask）baseline——目前完全缺失，必須先補上才能誠實宣稱 C3 贏過 B4。
3. 排查並解決 `Town01__dynamic_v3loop__runlong_fix4` 錄製上 ORB-SLAM3 拒絕 loop correction（`BAD LOOP!!!`）的根因，建立 loop-closure precision metric 的可用基礎。

---

## Verified Project Artifacts and Current Gaps

### Topic A — ORB-SLAM3 現況
- 位置：**不在本 repo**，獨立 workspace `~/orbslam_ws/`（已建置，最新 build 2026-07-02_14-55-07）。
- Wrapper fork：`~/orbslam_ws/src/orb-slam3-ros2/`（`NTU-iEV-M-Lab/orb-slam3-ros2`，18 個本地 commit；`stereo-slam-node.cpp`/`stereo-inertial-node.cpp` 今日有未 commit 的 TUM logger 修改）。
- Core：`orbslam3_core/lib/libORB_SLAM3.so`，vendored、非 submodule，未見 diff-from-upstream 工具。
- 已建置模式：mono/stereo/rgbd/rgbd-inertial/stereo-inertial 全部都在 `install/orbslam3/lib/orbslam3/`。KITTI 用 stereo；CARLA/EuRoC 用 stereo-inertial。
- Player：`scripts/paper2_carla_stereo_player_masked.py`、`scripts/kitti_tracking_stereo_player.py`、`scripts/kitti_oxts_to_tum.py`（本 repo 內）。
- 編排腳本：`run_orbslam_carla_logged.sh`、`run_orbslam_carla_pv_compare.sh`、`run_orbslam_euroc_logged.sh`、`run_orbslam_kitti_stereo.sh`、`run_orbslam_kitti_batch.sh`、`run_orbslam_towns_batch.sh`（皆用 `evo_ape` 算 ATE）。
- Trajectory/ATE 記錄：`logs/phase6/*.tum`、`phase6_orbslam3_kitti.csv`、`phase6_orbslam3_towns*.csv`、`phase6_orbslam3_vs_vins_carla.csv`、`PHASE6_ORBSLAM3_VS_VINS_CARLA_REPORT.md`（ORB-SLAM3 stereo-inertial 在一個高動態 CARLA 場景贏 VINS-Fusion，2.06 m vs 41.69 m ATE）、`PHASE6_ORBSLAM3_AUDIT.md`、`PHASE6_ORBSLAM3_REPAIR_PLAN.md`。
- **MapPoint/KeyFrame/keypoint 即時介面：不存在**（grep wrapper 節點內 `create_publisher`/`PointCloud`/`MapPoint` 為零）；只有逐幀 pose→TUM 檔案 + shutdown 時一次性 `SaveKeyFrameTrajectoryTUM`。
- 已知不穩定：shutdown 時 BA 會 hang，腳本皆用 SIGINT 後 SIGKILL 收尾。
- `src/VINS-Fusion-ROS2-jazzy`（本 repo 真正的估計器）：grep `ORB-SLAM3`/`orbslam` 為零命中，與 ORB-SLAM3 完全無關聯，符合「不碰 VINS」紅線。
- 既有 feasibility 文件（設計稿，未落地）：`paper2/track_a/PAPER2_ORBSLAM3_PV_LOCALIZATION_FEASIBILITY.md`。

### Topic B — Occupancy / Frontier / Nav2 現況
- 兩個候選 workspace：`~/nav2_ws`（已建置可跑）、`~/nstc_autonav_ws`（僅原始碼，**未建置**，不可直接執行）。
- Nav2 core：`nav2_ws/src/navigation2/` 完整 vendored 上游 clone；**無自訂 costmap yaml**，推定用 stock 預設值。
- rtabmap：`nav2_ws/src/rtabmap/`、`nav2_ws/src/rtabmap_ros/`（含 `rtabmap_costmap_plugins`），已建置。
- Frontier：`wavefront_explorer/wavefront_explorer/wavefront_frontier.py`（真實可跑，用 `GetCostmap`/`OccupancyGrid`/`FollowWaypoints`），已建置；配套節點 `goal_repeater.py`、`path_cost_monitor_node.py`（發布 `/path_cost_monitor/high_cost`）、`odom_bridge_node.py`、`twist_servo.py`、`scan_fix_node.py`、`camera_mux.py`。
- Depth→occupancy：`bev_sem2d_to_scan.py`（BEV semantic→合成 `LaserScan` `/bev/scan`，非完整 occupancy grid），上游 `bev_infer/bev_infer/bev_infer.py`、`bev_pcl.py`。
- **無自訂 dynamic obstacle cost layer plugin**。
- 最接近「object persistence」的既有模組：`nav2_ws/src/paper2_validity_bridge/`（`object_scan_synth_node.py`、`validity_publisher_node.py`、`validity_to_nav_adapter.py`、`mini_world_sim_node.py`、`fake_track_publisher_node.py`、`risk_behavior_logger_node.py`、`validity_logger_node.py`），已建置——但這是 risk bus，不是 anchor store。
- `my_robot_bringup`：僅一個檔案 `bt/my_hybrid_nav.xml`，無完整 bringup launch/params。

### Topic C — CARLA / KITTI 資料集現況
- CARLA 資料**不在本 repo**：`/mnt/sata4t/datasets/carla_fwvio/`（469 個 run，`carla_wheel.csv`+`.prov.json`+`.collect.log`）、`/mnt/sata4t/datasets/carla_vins/`（獨立收集樹）。Towns：01/02/04/05/06/07/10HD；11/12 一律 `CARLA_REC_CRASH`；08/09 在此 CARLA 版本不存在。
- 索引：`paper2_carla_dataset_status.tsv`、`logs/CARLA_TOWN_SCAN.md`、`logs/phase6/PHASE6_CARLA_*`。
- 情境命名對應：`sparse/medium/dense`×`b1/r30/r60/r90`=NPC 密度×spawn 半徑；`dynamic_v3r8` 的 `anchor_recovery_preview` 對應 collector 的 `npc_static_frac`（部分 NPC 永久停等=停等車情境，`~/fwvio_ws/scripts/collect_carla_v2.py:102,400,491`）；`low_texture`/`low_light`/`visual_outage` 明確標記；**唯一 return-visit/loop 錄製**＝`Town01__dynamic_v3loop__runlong_fix4`（900 m/248 s，GT loop closure 0.3 m@t=229s，`PHASE6_CARLA_LOOP_RECORDING_AND_ORBSLAM3_RESULT.md`，但 ORB-SLAM3 拒絕修正）。
- **無行人/walker actor**（collector grep 為零命中），**無明確 stop-and-go 旗標**（只有語意不明的 `npc_target_speed_frac`）。
- Replay/collector 腳本在**姊妹 workspace**，不在本 repo：`~/vins_ws/carla_dataset_replay_ros2.py`、`~/fwvio_ws/scripts/collect_carla_v2.py`；本 repo 內為 `scripts/paper2_carla_stereo_player_masked.py`、`scripts/run_orbslam_carla_logged.sh`、`scripts/run_orbslam_towns_batch.sh`。
- KITTI：`/mnt/sata4t/datasets/kitti/{odometry,raw,tracking}`；player 在本 repo `scripts/kitti_tracking_stereo_player.py`、`scripts/kitti_oxts_to_tum.py`。

### Topic D — Object Labeling / Tracking / Mask 現況
- Per-det CSV：`outputs/paper2_perdet(_v2)/`，欄位與規格吻合（`track_id, cls, conf, bbox_w/h, disp_med/std, depth_m, range_m, bearing_deg, raw_speed_ms, gt_range_m, gt_speed_ms, speed_err_ms, dist_bin`）。
- Mask JSON：`logs/phase6/stereo_mask_dense_{oracle,tcsvm,all_dynamic,validity_aware}.json`；生成器 `phase6_make_stereo_mask.py`、`paper2_make_vins_masks.py`、`paper2_make_tcsvm_mask.py`、`paper2_make_random_mask.py`——**均非幾何/光流法**，B4 baseline 缺失（見第 7 節）。
- TCSV/PV：`scripts/paper2_tcsv_features.py`、`paper2_tcsv_train_eval.py`、`paper2/PAPER2_TCSV_RESULTS.md`。
- Object validity 資料集：`paper2_v5_validity_with_ovi.parquet`、`paper2_v5_object_validity_dataset.parquet`、`paper2/paper2_kitti_validity_dataset.csv`、`paper2/nuscenes/paper2_nuscenes_validity_dataset.csv`。
- 偵測/追蹤：**真實 YOLOv8m + Ultralytics ByteTrack**（`scripts/paper2_raw_object_probe.py`），深度用 OpenCV SGBM（真實立體匹配，非 GT），GT 只用於 ego-motion 補償與誤差稽核（`gt_range_m`/`gt_speed_ms`），不驅動估計本身。
- 缺口：無像素級 segmentation mask（僅 bbox 級 YOLO + 手工/GT 立體 bbox mask）。

### Topic E — Closed-Loop Pipeline 現況
- `paper2_ab_nav.launch.py` 存在（`nav2_ws/src/paper2_validity_bridge/launch/`）；文件中提到的 `paper2_carla_replay_demo.launch.py` **在目前檔案樹中找不到**（可能已移除/更名）。
- `PAPER2_PHASE2_CARLA_CLOSEDLOOP_DRYRUN.md` 明確自陳這是 **dry-run，非正式 A→B**：ego pose/map 是 stub，`/scan` 由物體 GT 合成（CARLA 無 lidar），Nav2 從未被給 goal。
- `PAPER2_PHASE3_AB_NAV_RESULTS.md` 的 A/B/C 比較**繞過 Nav2**，用 `mini_world_sim` 自製 potential-field controller（因完整 `navigation_launch` 在批次環境下 ~11.5s 後退出）；結果 ours 策略 0 起近碰撞 vs baseline 69/88，但單一固定場景、無 seed 掃描。
- CARLA synchronous_mode+固定 seed 的邏輯只在**姊妹 workspace** `~/fwvio_ws/scripts/collect_carla_v2.py`（`synchronous_mode=True`、`fixed_delta_seconds=0.01`、`seed=hash(town+condition+run)`），本 repo 與 `nav2_ws` 內都沒有這段邏輯。
- 多 seed 掃描（Phase 17）是**決策層合成掃描**，非 CARLA/Nav2 真閉環；另有 24-run CARLA 掃描（Town02/03/04 會 crash）。
- `ROUTE_C_STATUS.md`（`logs/ROUTE_C_STATUS.md`）與 frontier 無關，是 VINS 輪速里程計 ATE 決定性工作。

### Topic F — Label Timing / Edge AI Budget 現況
- 全 repo 僅一處 `ApproximateTimeSynchronizer`（`bev_infer.py`，與 object persistence 無關）；`paper2_validity_bridge`/`wavefront_explorer`/VINS 均無 timestamp 同步機制，各 topic 各自獨立 rate。
- 已知 Hz（零散分佈於各文件，無單一權威表）：`/object_validity` 5Hz、合成 `/scan` 10Hz、stub `/odom` ~30Hz、`/path_cost_monitor/high_cost` ~5Hz、`/cmd_vel_2` ~30Hz、VINS reliability logger ~10Hz/keyframe、CARLA IMU 100Hz/影像 20fps；**costmap 更新率、frontier replan 週期、local planner 執行率皆無文件化數字**。
- 硬體：`nvidia-smi` 回報 RTX 5090（桌上型）；`Jetson`/`Orin`/`GX10` 全 repo 零命中，無 edge 硬體目標或量測基礎。

---

## 缺口彙總（優先序，供裁示參考）

1. **ORB-SLAM3 無 live MapPoint/KeyFrame 介面**——本方向的架構前提目前完全不存在，是最大單一缺口。
2. **B4（geometric/optical-flow mask）baseline 缺失**——連 competitor baseline 都沒有，無法誠實宣稱 C3 更好。
3. **真正 closed-loop A→B 尚未存在**——現況只有 dry-run（stub ego/map+合成 scan）與繞過 Nav2 的自製 controller 兩種代用品。
4. **Label timing/async contract 全新**——現有 stack 完全沒有 timestamp 同步先例。
5. **行人/穿越情境 CARLA 錄製缺失**——two-sided gate 若需要 pedestrian crossing，現有 469 run 都是純車輛 NPC。
6. **Edge AI budget 無量測基礎**——開發機是桌上型 RTX 5090，非 Jetson 等級。
7. **與現行 PI 裁示（禁開新 branch、聚焦 OPL 論文）方向未對齊**——啟動前需使用者重新裁示（見第 0 節）。
