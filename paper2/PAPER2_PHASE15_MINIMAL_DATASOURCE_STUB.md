# PAPER2_PHASE15_MINIMAL_DATASOURCE_STUB — closed-loop stub data source

> 任務 C：在 G5 顯示 frontier/Nav2 graph「起得來但餓著」(`/map //odom //scan` publisher=0) 之後，補一個**最小資料源 stub**，讓 graph 不再 hungry。
> **嚴正聲明：這不是正式物理模擬、不是正式 A→B 實驗。** 只是讓 subscriber 接得上、counts 非 0 的 closed-loop stub。**不得把跑在此 stub 上的數字當作導航效能。**

## 1. 元件
- node：`minimal_source`（`paper2_validity_bridge/minimal_source_node.py`）
- launch：`minimal_datasource.launch.py`（arg `drive:=false|true`）

## 2. 發布內容
| Topic / TF | 型別 | 內容（stub） |
|---|---|---|
| `/map` | `nav_msgs/OccupancyGrid` | 200×200 @ 0.1m = 20m 方形，內部全 free(0)、外框 occupied(100)，latched(TRANSIENT_LOCAL) |
| `/odom` | `nav_msgs/Odometry` | 原點靜止（`drive:=true` 時極慢前移到 2m 上限），30Hz |
| `/scan` | `sensor_msgs/LaserScan` | 360 beams，等距固定 5m，range_max 20m，10Hz |
| tf `map→odom` | static | identity |
| tf `odom→base_link` | dynamic | 跟隨 odom x，30Hz |

參數：`map_size`、`map_resolution`、`scan_range`、`odom_rate_hz`、`scan_rate_hz`、`drive`。

## 3. 驗證（實測 2026-06-30，domain 77 獨立）
| 檢查 | 結果 |
|---|---|
| `/map` publisher count | **1**（原 0） ✅ |
| `/odom` publisher count | **1**（原 0） ✅ |
| `/scan` publisher count | **1**（原 0） ✅ |
| `/tf` 發布率 | ~30 Hz ✅ |
| `/map` info | resolution 0.1, width/height 200 ✅ |
| `/odom` header.frame_id | `odom` ✅ |
| `/scan` range_max | 20.0 ✅ |

→ **成功條件達成**：`/map //odom //scan` publisher count 不再是 0；frontier/Nav2 啟動時可看到資料源，graph 不再 hungry。

## 4. 重現指令
```bash
source /opt/ros/jazzy/setup.bash && source ~/nav2_ws/install/setup.bash && export ROS_DOMAIN_ID=68
# 終端 1：stub 資料源
ros2 launch paper2_validity_bridge minimal_datasource.launch.py          # 或 drive:=true
# 終端 2：原版 frontier/Nav2（不改 code）
ros2 launch wavefront_explorer full_system.launch.py
# 終端 3：確認不再 hungry
ros2 topic info /map     # Publisher count: 1
ros2 topic info /odom    # Publisher count: 1
ros2 topic info /scan    # Publisher count: 1
```

## 5. 限制（誠實）
- 固定 free-space map + 靜止 odom + 常數 scan＝**無真實幾何/動力學**；frontier 在此不會有有意義的探索行為，只是「不缺資料」。
- 真正 A→B 閉環需要真模擬器（CARLA/Isaac/Gazebo）或 bag + 真 VIO odom；此 stub 僅為後續整合的接線測試底座。
- map→odom / odom→base_link 皆 identity，無定位誤差模型；GPS-denied 漂移行為未模擬。
