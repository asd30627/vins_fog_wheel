# PAPER2_PHASE3_AB_NAV_RESULTS — A→B 閉環導航（A/B/C）

> Phase 3：真正讓機器人**被控制器驅動**從 A 走到 B（非 Phase 2 的 playback），量 A/B/C 三 policy 的導航結果差異。
> **嚴正定位**：使用 mini_world_sim 內建的**最小 2D potential-field 控制器（NOT Nav2）**。完整 Nav2-planner-in-the-loop 因 batch harness 下 heavy launch 存活問題未完成（見 §5），核心 validity 效果用此最小控制器展示。
> **紅線守住**：A/B/C **只差 `validity_publisher` 的 policy**；控制器邏輯與參數三組**完全一致**（只有 validity-derived per-object risk 不同）；未改 Nav2 planner / 未碰 VINS / 無 live detector。

---

## 1. 場景
- A=(0,0) → B=(9,0)，直線路徑 y=0。
- 4 障礙；**兩個退化(deg)障礙落在路徑上** (4.2,0)、(7.3,0)：低 parallax → ours 判 `unobservable`、baseline 判可信。靜止 box (2.5,0.7) 與橫越 ped (6.0,0.8) 偏離路徑、三組看法一致。
- 障礙觀測性 profile 校準到 CARLA V5 class 分布（非 CARLA replay）。

## 2. 控制器（三組一致）
- 內建 potential-field：吸引到 B + 障礙斥力；斥力 margin 與速度由**每物件 validity risk**（來自 `/paper2/validity_debug`，policy 決定）調制。
- 流程：mini_world_sim 發 `/object_tracks` → `validity_publisher(policy)` → `/object_validity` → adapter → `/paper2/validity_debug`(per-object risk) → mini_world_sim 用 risk 放大避障 margin + 降速。
- 固定參數（三組相同）：base_margin 0.5、risk_margin_gain 1.4、risk_slow_gain 0.5、near_collision 門檻 0.6m（與控制 margin 脫鉤的穩定安全指標）、collide 0.35m、goal-dominant 加權 1.4/1.0。

## 3. 結果（`paper2_phase3_ab_nav.csv`，72s 上限）

| policy | success | time_to_goal (s) | path (m) | min_clearance (m) | collisions | **near_collisions** |
|---|---|---|---|---|---|---|
| always_full | 1 | 15.9 | 8.80 | 0.557 | 0 | **69** |
| distance_gate | 1 | 15.0 | 8.80 | 0.514 | 0 | **88** |
| **ours** | 1 | 29.1 | 9.50 | **0.895** | 0 | **0** |

## 4. 解讀
- **三組都抵達 B**（success=1）。差異在**安全**：
  - always_full / distance_gate **把路徑上的不可觀測障礙當可信**（risk≈0）→ 直接貼近通過 → **69 / 88 次 near-collision**、最小間距 ~0.5m。distance_gate 最差（純距離，近距更敢信）。
  - **ours** 對不可觀測障礙給高 risk → 放大避障 margin → **0 次 near-collision、最小間距 0.895m（≈1.6× 安全）**。
- **代價**：ours 多花 ~13s（29 vs 15）、多走 ~0.7m。
- **誠實結論**：selective validity 在 A→B 導航把「對退化動態/不可觀測障礙的過度信任」換成**更保守、更安全的繞行**，代價是時間/路徑，且仍成功到達。這正是 refusal/conservative policy 應有的 speed-vs-safety 取捨，與 Phase 1.7 決策層結果（ours 拒絕不可觀測速度）一致地延伸到**導航行為層**。

## 5. 限制（誠實，重要）
1. **不是 Nav2 閉環**：用 mini_world_sim 內建最小 potential-field 控制器。完整 Nav2 navigation_launch 在此 batch harness 下 heavy launch 約 11.5s 後即整組退出（G5 的 full_system 背景可活 45s，但本 A→B launch + `use_sim_time:=False` 不穩；mini_world_sim 單獨可活 ≥19s，故非我節點問題）。Nav2-planner-in-the-loop 留待有互動式 terminal 的環境。
2. **單一場景 / 確定性單跑**：固定障礙佈局、無多 seed/隨機化；mini_world_sim 確定性（重跑同結果）。多佈局 + 統計待補。
3. **合成障礙**：觀測性 profile 校準到 CARLA V5 分布，非 CARLA frame replay（真實 validity replay 見 Phase 2 dry-run）。
4. **near-collision 門檻 0.6m / collide 0.35m**：固定且與控制 margin 脫鉤，但仍為選定值；collisions 全 0（障礙非致命，差異在 near-miss）。
5. 控制器參數為一組合理固定值（三組一致），非窮舉調校；不同參數會改變 trade-off 幅度，但「ours 較保守較安全」方向穩健（已見於 aggressive 與本設定）。

## 6. 重現
```bash
source /opt/ros/jazzy/setup.bash && source ~/nav2_ws/install/setup.bash
bash ~/nav2_ws/src/paper2_validity_bridge/scripts/run_phase3_ab_nav_sweep.sh
cat ~/fwvio_estimator_ws_wheel/paper2_phase3_ab_nav.csv
```

## 7. 與整體故事的銜接
- Phase 1.6：risk-bus → 真實停車行為（未改 twist_servo）。
- Phase 1.7：決策層 ours 拒絕不可觀測速度，多 seed 穩健。
- Phase 2：真實 V5 validity 流經真 frontier/Nav2（dry-run）。
- **Phase 3（本檔）：A→B 導航層，ours 用 validity 換得更安全的繞行**（最小控制器；Nav2-in-loop 待補）。
