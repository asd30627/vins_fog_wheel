# PAPER2_PHASE15_BASELINE_POLICY_SWEEP — A/B/C policy sweep

> 任務 A+B：在 `paper2_validity_bridge` 內把 baseline A/B 與 ours C 做成 `validity_publisher` 的 `policy` 參數，用同一套 adapter + 同一組 fake tracks 跑出決策層差異。
> **紅線守住**：A/B/C **只改 `validity_publisher` 的 `policy`**；`validity_to_nav_adapter` 規則、D0/D1/D2 fake tracks、planner 全部不動；distance_gate 的 `d0` 固定 10.0m，**未為 ours 調參**。

---

## 1. 三組 policy（只差分類來源）
| policy | 規則 | 觀測性 hint |
|---|---|---|
| **A always_full** | 非靜止物全部 `full_state`、`velocity_valid=true` | 忽略 |
| **B distance_gate** | `range < d0(10m)` → full_state；否則 position_only | 只用距離 |
| **C ours** | selective validity（speed/parallax/range/depth_jitter/bearing 規則 → 5-class） | 使用 |

共用：`fake_track_publisher`(D0 static / D1 等速橫越 / D2 退化三模式)、`validity_to_nav_adapter`、`paper2_validity_logger`。

## 2. 結果（固定 duration=18s, tracks=all, d2_period=2s；`paper2_phase15_policy_eval.csv`）

| 指標 | A always_full | B distance_gate | C **ours** |
|---|---|---|---|
| full_state_count | 175 | 218 | 95 |
| position_only_count | 110 | 64 | 110 |
| invalid_velocity_count | 0 | 0 | **50** |
| unobservable_count | 0 | 0 | **30** |
| high_cost_count | 0 | 0 | **30** |
| **D1_valid_velocity_retained** | 95 | 94 | **95** |
| **D2_wrong_velocity_accepted** | **80** | 30 | **0** |
| **D0_static_wrongly_predicted** | 0 | **94** | **0** |
| max_risk | 0.1 | 0.1 | **0.9** |

(validity_msgs ≈ 95 三組一致 → 可直接比較計數)

## 3. 解讀
- **A always_full**：對 D2 退化物**全盤接受錯誤速度（D2_wrong=80，最差）**，且永不舉 risk（high_cost=0, max_risk=0.1）。「永遠輸出 velocity」的代價可量化。
- **B distance_gate**：純距離 → **把範圍內所有靜止物也當可動（D0_static_wrongly_predicted=94，最差）**，且對近距退化物（D2 sudden_stop 在 10m 內）仍誤收 30；同樣不舉 risk。
- **C ours**：**D2_wrong=0、D0_static=0**，唯一同時拒絕「退化動態速度」與「靜止物速度預測」；改以 invalid_velocity(50)+unobservable(30) 表達拒絕，並把 risk 抬到 0.9、high_cost 觸發 30 次（接既有 frontier risk-bus）。

## 4. 成功條件核對
| 成功條件 | 結果 |
|---|---|
| 三個 policy 都可 launch | ✅ |
| always_full 在 D2 出現 wrong_velocity_accepted | ✅ **80** |
| distance_gate 在 D1 降低 valid_velocity_retention | ⚠️ **未呈現**（見 caveat）；其缺陷改以 **D0_static_wrongly_predicted=94** 呈現 |
| ours 保留 D1 full_state 且拒絕 D2 velocity | ✅ D1 retained **95** / D2_wrong **0** |

### Caveat（誠實，不調參硬湊）
- D1 等速橫越的 range 恆 ≤5.83m，固定 `d0=10m` 下 distance_gate **必然保留 D1**，故 valid_velocity_retention 未被降低（94≈95）。
- 此為「成功條件用『可能』」的真實落點：**我們不為了讓 distance_gate 輸而縮小 d0 或把 D1 推遠**（會違反紅線/公平性）。distance_gate 的真實弱點在這組幾何下表現為「靜止物誤預測」，已被指標清楚捕捉。
- 若日後要展示 distance_gate 的 D1 retention 弱點，正解是換更遠/分段的 D1 軌跡或更大 d0，**並對三組一致套用**，而非單獨調 ours。

## 5. 重現指令
```bash
source /opt/ros/jazzy/setup.bash && source ~/nav2_ws/install/setup.bash && export ROS_DOMAIN_ID=68
# 一鍵 sweep（自動跑三組 + 合併 summary）
bash ~/nav2_ws/src/paper2_validity_bridge/scripts/run_phase15_policy_sweep.sh
cat ~/fwvio_estimator_ws_wheel/paper2_phase15_policy_eval.csv

# 或單組手動：
ros2 run paper2_validity_bridge fake_track_publisher --ros-args -p enabled_tracks:=all -p d2_mode_period_s:=2.0 &
ros2 run paper2_validity_bridge validity_publisher --ros-args -p policy:=ours &      # 或 always_full / distance_gate
ros2 run paper2_validity_bridge validity_to_nav_adapter &
ros2 run paper2_validity_bridge paper2_validity_logger --ros-args -p policy_label:=ours -p output_csv:=/tmp/ours.csv &
```

## 6. 輸出檔
- `paper2_phase15_policy_eval.csv`（合併 summary，3 列）
- `outputs/phase15/policy_{always_full,distance_gate,ours}.csv`（單組）
- script：`scripts/run_phase15_policy_sweep.sh`

## 7. 限制
- synthetic validity 是幾何 proxy，非學習模型，數字非真實 CARLA。
- 計數比較未跑多 seed/CI；下一步可加重複 + 統計（McNemar/Wilcoxon，見 eval protocol）。
- 尚未在真 frontier 閉環上量「導航行為」差異（需 stub 以外的真資料源）。
