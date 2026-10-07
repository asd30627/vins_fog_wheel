# PAPER2_PHASE17_MULTISEED_STATS — 多 seed 決策層統計 gate

> 任務 B / Phase 1.7：把 A/B/C 三 policy 在**多 seed**下跑，給決策層指標 mean±std + 配對 dominance，判斷統計穩健。
> **Gate 規則**：1.7 沒通過，不得宣稱統計穩健。
> **紅線守住**：A/B/C 只差 `validity_publisher` 的 policy；seed 只變 `fake_track_publisher` 的觀測性抖動+時間相位（同 seed → 三組看到**完全相同**的 tracks，公平配對）；planner/adapter/閾值未為 ours 調。

---

## 1. 方法
- seeds = {1,2,3,4,5}，每 (seed×policy) 跑 12s，`enabled_tracks=all`，`d2_mode_period_s=2.0`。
- seed 機制：`fake_track_publisher` 對觀測性 hint（parallax / bearing_change_rate / depth_jitter / range）做 ±20% seeded 抖動 + per-seed 時間相位偏移；**speed 不抖**（保持 D0/D1/D2 類型穩定）。policy-independent。
- 聚合：`aggregate_phase17.py` → 每 policy mean±std + 配對 dominance + gate 判定。
- 15 個 per-run CSV：`outputs/phase17/policy_<policy>_seed_<seed>.csv`；彙整：`paper2_phase17_multiseed_summary.csv`。

## 2. 結果（n_seeds=5）

| policy | **D2_wrong_velocity_accepted** (mean±std) | **D1_valid_velocity_retained** | **D0_static_wrongly_predicted** | high_cost (mean) | invalid_vel | unobservable | max_risk |
|---|---|---|---|---|---|---|---|
| always_full | 55.0 ± 0.0 | 65.0 ± 0.0 | 0.0 | 0.0 | 0 | 0 | 0.1 |
| distance_gate | 21.0 ± 1.3 | 64.0 ± 0.0 | **64.0** | 0.0 | 0 | 0 | 0.1 |
| **ours** | **0.0 ± 0.0** | 64.2 ± 0.4 | **0.0** | 22.6 | 31.6 | 22.6 | 0.9 |

## 3. 配對 dominance（同 seed 比較）
- `ours D2_wrong < always_full`：**5/5 seeds**
- `ours D2_wrong < distance_gate`：**5/5 seeds**
- D1 retention：ours 64.2 vs baseline_max 65.0 → **≥0.95×，未變差**

## 4. Gate 判定：✅ **PASS**
判準（程式碼內）= `ours D2_wrong < 兩 baseline 於每個 seed` ∧ `ours D1_retain ≥ 0.95×baseline_max`。
- ours 在**所有 seed**皆 D2_wrong=0（std 0）且 D0_static=0；always_full（55）與 distance_gate（21）每個 seed 都被 ours 完勝；D1 retention 持平。
- 結論：ours 的「拒絕退化動態速度 + 不誤預測靜止物」在觀測性抖動下**穩健**（非單一 seed 僥倖）。允許宣稱統計穩健（在此 synthetic 範疇內，見限制）。

## 5. 重現
```bash
source /opt/ros/jazzy/setup.bash && source ~/nav2_ws/install/setup.bash
SEEDS="1 2 3 4 5" bash ~/nav2_ws/src/paper2_validity_bridge/scripts/run_phase17_multiseed.sh
cat ~/fwvio_estimator_ws_wheel/paper2_phase17_multiseed_summary.csv
# 或重新聚合既有資料：
python3 ~/nav2_ws/src/paper2_validity_bridge/scripts/aggregate_phase17.py
```

## 6. 限制（誠實）
- 「seed」是**synthetic 觀測性抖動**，非真實感測噪聲；穩健性結論限於此 proxy 範疇，真實穩健性須在 Phase 2 真資料重驗。
- dominance 是非參數 sign-test（5/5），未做大樣本 Wilcoxon（n=5）；std 多為 0 因 ours 行為確定性。可加更多 seed/更大抖動做更強統計。
- 指標是計數（frame×object），非導航結果；導航層效能須等 Phase 2 + gate 全過。
