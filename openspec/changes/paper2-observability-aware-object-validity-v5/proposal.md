## Why

Paper-2 從 v4「VIWO-conditioned NOUE」轉為 **v5「Observability-Aware Dynamic Object State Validity for GPS-Denied Navigation」**。

**轉向理由（證據驅動，見 `PAPER2_V4_TO_V5_EVIDENCE_MAP.md`）：**
- v4 的核心賭注 A2（物體可信度 conditioned on VINS quality，feature concat）**經嚴格測試不成立**：sensor-frame ablation FAILED（VINS features 與 object features 冗餘），world-frame WEAK（校準反變差、被 VINS scale 發散汙染）。把「定位品質」當額外 feature 串接進 error-regression 不穩且冗餘。
- 但既有資料**反而強烈支持 observability/validity 切角**：matched 物體的 velocity validity 隨幾何崩潰（0-15m 僅 0.38、15-30m 0.16、30m+ 0.06），position validity 退化較緩（0.89→0.73→0.30）；30m+ velocity 是 garbage（spd_err p95 ~410 m/s）；yaw error 被 range 放大（`e_lat≈r·sin Δψ`）；v4 refusal policy 已證實降過度自信錯誤 velocity（0.59→0.39）。

**v5 主張：** 不是每個動態物體狀態都應該硬估。在 GPS-denied 常見道路幾何下，object velocity（甚至 full state）可能 weakly observable 或 unobservable。與其永遠輸出一個可能錯的 velocity，本研究提出**observability-aware validity layer**，判斷何時輸出 full-state / position-only / invalid-velocity / unobservable / conservative-warning。

**心態（不過度否定也不過度宣稱）：** 文獻有 uncertainty / risk tube / dynamic SLAM / motion segmentation，但我們找的是**問題定義、方法切角、實驗任務、輸出用途**的差異，不是字眼從未出現。不主打 conformal risk tube / generic pose-uncertainty / dynamic SLAM / object factor / VINS-quality concat；主打 dynamic-object **observability/validity + refusal-aware perception + invalid-velocity detection + observability phase map**。

## What Changes

四個 contribution（細節在 design.md），全用**現有 24-run dataset + benchmark + VINS replay 結果**，不重錄、不碰 backend：

- **C1 — Observability/validity phase map**：把既有 raw object benchmark 轉成「哪些 regime（distance×density×bearing-change×depth-quality×yaw-lever×track-age）是 full-state observable / velocity-invalid / position-only / conservative-warning」。
- **C2 — Observability Validity Index (OVI)**：一個**幾何可解釋**指標（非 black-box MLP），含 `yaw_lever=range·sin(yaw_sigma)`、`bearing_change_rate`、`depth_noise_proxy(disparity med/std)`、`velocity_observability_proxy=bearing_change/range`，輸出 `OVI_position / OVI_velocity / OVI_full_state`。
- **C3 — Refusal-aware dynamic object state policy**：levels = full_state / high_covariance / position_only / velocity_invalid / unobservable / conservative_warning；以 invalid-velocity recall/precision、overconfident-wrong-velocity、false-refusal、planner-usable ratio 評估。
- **C4（optional，加分）— Object-consistency ego-degradation diagnostic**：多物體一致的假 lateral velocity pattern 與 VINS scale/yaw 退化的相關性，當 independent ego-degradation alert（offline，不回饋 VINS）。效果不明顯就誠實標 weak。

## Capabilities

### New Capabilities
- `paper2-observability-aware-object-validity-v5`：GPS-denied 下動態物體狀態的 observability-aware validity layer——observability/validity phase map、幾何可解釋 OVI、refusal-aware state policy、optional object-consistency ego diagnostic。標準 red lines（不改 VINS backend、不加 object factor、不做 G3 scaffold、不重錄、不以 conformal risk tube 為主創新、不宣稱 first/localization improvement）。

### Modified Capabilities
<!-- None deleted. v4 (paper2-viwo-conditioned-noue-v4) 與 G0 change 保留為證據/負結果。v5 是切角轉換的新 capability，沿用 v4 的 G0/G1 data + benchmark + VINS replay 產物。 -->

## Impact

- **零 backend 改動**：所有 v5 產物為 standalone scripts + reports，消費既有 CSV/parquet。
- **資料**：`paper2_raw_object_benchmark_all.csv`(20921)、`_with_vins.csv`、24-run dataset、VINS replay reliability/vio。不重錄 CARLA（除非明確缺）。
- **新增 standalone**：`scripts/paper2_v5_{build_validity_labels,observability_index,refusal_policy,object_consistency_ego_diagnostic}.py`；報告 `PAPER2_V5_{VALIDITY_LABEL_REPORT,OVI_RESULTS,REFUSAL_POLICY_RESULTS,OBJECT_CONSISTENCY_EGO_DIAGNOSTIC,LITERATURE_POSITIONING}.md` + `PAPER2_OBSERVABILITY_AWARE_V5_SUMMARY.md` + `PAPER2_V4_TO_V5_EVIDENCE_MAP.md`。
- **誠實**：閾值寫在 report（可 ablation，非絕對）；不過度 claim；不刪 v4 負結果；C4 弱就標 weak。
- **Gate**：完成 v5 spec + prototype + summary 後 STOP，等使用者 design checkpoint；不自動進 backend / 不自動定稿主題。
