# PAPER2_PHASE16_RISK_BUS_BEHAVIOR — risk-bus 行為 gate

> 任務 A / Phase 1.6：證明 adapter 發出的 `/path_cost_monitor/high_cost` **真的改變導航行為**，而非只是一個沒人理的 topic。
> **Gate 規則**：1.6 沒通過，不得宣稱 risk-bus 造成導航行為變化。
> **紅線守住**：用的是**未修改**的 frontier 節點 `twist_servo`；不改 planner/VINS；A/B/C 只差 `validity_publisher` 的 policy。

---

## 1. 機制（為何這能證明行為變化）
G5 已知 `twist_servo`（frontier 原碼）訂閱 `/path_cost_monitor/high_cost`：
- `high_cost=True` → `safety_stop=True` → `control_loop` 直接 publish `/cmd_vel_2 = 0`（停車）。
- `high_cost=False` → 正常把 `/cmd_vel` 經前饋/PI 轉成 `/cmd_vel_2`（前進）。

測試裝置（皆現成、未改 code）：
```
minimal_source(/odom) ─┐
ros2 topic pub /cmd_vel (forward 0.5) ─┤→ [twist_servo 原碼] → /cmd_vel_2
our bridge: fake_track(all) → validity_publisher(policy) → adapter → /path_cost_monitor/high_cost ─┘
risk_behavior_logger: 訂閱 high_cost + /cmd_vel_2 → 相關性計數
```

判讀規則（每個 `/cmd_vel_2` 樣本）：
- high_cost True & |v|<eps → `stopped_on_risk`（risk-bus **成功停車**）
- high_cost True & |v|≥eps → `moved_on_risk`（risk-bus **失效**）← gate 要求 = 0
- high_cost False & |v|≥eps → `moved_when_safe`（safe 時前進）
- high_cost False & |v|<eps → `stopped_when_safe`（idle/誤停）

## 2. 結果（`paper2_phase16_behavior.csv`，duration 22s，eps 0.02 m/s）

| policy | high_cost_true | cmd2_msgs | stopped_on_risk | moved_on_risk | moved_when_safe | stopped_when_safe | **gate_1_6_pass** |
|---|---|---|---|---|---|---|---|
| always_full | 0 | 689 | 0 | 0 | 677 | 12 | 0 |
| **ours** | 40 | 688 | **240** | **0** | 437 | 11 | **1** |

## 3. Gate 判定：✅ **PASS（經 ours 證明）**
- **ours**：high_cost 觸發 40 次 → `/cmd_vel_2` 被強制歸零 **240 個樣本**（stopped_on_risk），**moved_on_risk=0**（每次 risk 都確實停下），且 safe 時前進 437 個樣本 → **gate_1_6_pass=1**。
- **always_full**（對照）：從不產生 high_cost（high_cost_true=0），故無 risk 停車（stopped_on_risk=0），機器人正常前進（moved_when_safe=677），**moved_on_risk=0**（無 false 行為）。其 gate=0 是「無 risk 可act」的 trivial 情形，正是對照組該有的樣子。

**結論**：`/path_cost_monitor/high_cost` 對**未修改的** frontier `twist_servo` 造成**可量測、確定性、policy 驅動**的停/走行為改變。允許宣稱「risk-bus 造成導航行為變化」。

## 4. 重現
```bash
source /opt/ros/jazzy/setup.bash && source ~/nav2_ws/install/setup.bash && export ROS_DOMAIN_ID=68
bash ~/nav2_ws/src/paper2_validity_bridge/scripts/run_phase16_risk_behavior.sh
cat ~/fwvio_estimator_ws_wheel/paper2_phase16_behavior.csv
```

## 5. 限制（誠實）
- `/cmd_vel` 是常數前進、`/odom` 來自 minimal_source stub → 這證明的是「risk-bus → 安全停車閘」的**因果連線**，**不是**真實 A→B 導航效能（後者見 Phase 2，且須 gate 全過才列主結果）。
- 只測 `twist_servo` 這條 risk-bus 分支；`goal_repeater`（換 frontier 點）分支未在此量化，列為後續。
- ours 的 high_cost 來自 D2 退化物（unobservable），屬 synthetic track，非真實感知。
