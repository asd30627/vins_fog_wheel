# PAPER2 V4 → V5 EVIDENCE MAP (2026-06-30)

> 把 v4「VIWO-conditioned NOUE」的既有結果，映射到 v5「Observability-Aware Dynamic Object State Validity」。
> 目的：證明 v5 不是換包裝，而是**既有證據本身就指向 observability/validity，而非 feature-conditioning**。未刪 v4，未把 A2 說成成功。

## 1. v4 做了什麼（已完成、保留）
- G0 data grounding：CARLA dynamic_v3 **24-run balanced dataset**（Town10HD+Town01 ×3 density ×4 spawn @400f，含 per-object position/bbox/class/depth/seg GT）。
- G1 raw object benchmark：YOLOv8m+SGBM+ByteTrack，**20921 偵測 / 15811 GT-matched**，距離分 bin 誤差 + phase map v0（`PAPER2_RAW_OBJECT_BENCHMARK.md`、`PAPER2_PHASE_MAP_V0.md`）。
- G2 NOUE-object：uncertainty/observability/utility heads（`PAPER2_NOUE_G2_RESULTS.md`）；output policy（`PAPER2_OUTPUT_POLICY_RESULTS.md`）；H1 隔離（無改善）。
- A2（核心 v4 賣點）：VINS replay 24/24 + join 95.3% + 兩種 ablation（`PAPER2_DAYTIME_A2_SUMMARY.md`、`PAPER2_A2_VINS_CONDITIONING_RESULTS.md`）。

## 2. v4 A2 為什麼不 promising（誠實，非藉口）
- **Test 1（sensor-frame, GT ego-comp）= FAILED**：加 VINS-quality features 全面變差（NLL 62→127、AUROC 0.555→0.484）。原因：object 觀測 features（range/depth/disparity variance/bbox）已編碼物體可靠度，VINS 定位品質對 sensor 誤差**冗餘**。
- **Test 2（world-frame, VINS 誤差傳播）= WEAK**：only 邊際 AUROC（degraded 0.591→0.614），但 NLL/ANEES/ECE 反變差，且被 VINS scale 發散（0.77–5.0×）artifact 汙染。
- **教訓**：把「定位品質」當**額外 feature 串接**進一個 error-regression 模型不穩、且冗餘。→ 應該改成**結構化的 observability/validity 判準**（幾何可解釋），而不是 black-box feature conditioning。**這正是 v5 的切角。**

## 3. 哪些 v4 結果**反而支持 v5**（核心論據）

### 3.1 velocity 經常不可信，且隨幾何崩潰 — v5 的主論據
matched 物體的 validity（`paper2_raw_object_benchmark_all.csv`，pos_valid=pos_err≤3m；vel_valid=spd_err≤3 且 dir_err≤45°）：

| distance bin | n | **pos_valid** | **vel_valid** | spd_err med (m/s) | dir_err med |
|---|---|---|---|---|---|
| 0-15m | 1863 | 0.89 | **0.38** | 1.6 | 5.7° |
| 15-30m | 4164 | 0.73 | **0.16** | 3.2 | 17.2° |
| 30m+ | 9784 | 0.30 | **0.06** | 8.0 | 65.6° |

- **velocity validity 連近距只 0.38，遠距崩到 0.06** → 「永遠輸出 velocity」是錯的。這是 v5「refusal-aware / invalid-velocity」的直接證據。
- **position validity（0.89→0.73→0.30）退化較緩** → 「position-only」是一個真實且有用的 regime（pos 可信但 vel 不可信，尤其 0-15/15-30m）。
- → 三段式 validity（full-state / position-only / invalid-velocity-or-unobservable）**由資料浮現，不是硬塞**。

### 3.2 30m+ velocity 是 garbage（量級證據）
- raw benchmark：spd_err median 7.98 m/s（30m+），**p95 達 ~410 m/s（物理不可能）**；dir_err median 65.6°（≈亂猜）。→ 遠距 velocity 不可觀測，應拒絕輸出。

### 3.3 yaw error 被 range 放大（幾何 lever，OVI 的核心項）
- `e_lat ≈ range · sin(Δψ)`（per-detection 已量；30m+ median range ~58m → 1° ego-yaw ≈ 1.0m 物體 lateral 誤差）。→ OVI 的 `yaw_lever = range·sin(yaw_sigma)` 有實證基礎。

### 3.4 refusal 政策已證實能降過度自信錯誤 velocity
- v4 output policy：overconfident-wrong-velocity **0.586→0.387**（↓34%），risk-cov 29.0→25.1，usable 0.90（`PAPER2_OUTPUT_POLICY_RESULTS.md`）。→ v5 C3 refusal policy 有 v4 baseline 可比、且方向已驗證有效。

### 3.5 VINS-quality concat 不穩 → 改 observability/validity（切角轉換）
- A2 兩測法都不穩（§2）→ 不該做 feature-conditioning；應做**幾何可解釋的 observability index（OVI）+ validity labels + refusal policy**。VINS reliability features 在 v5 降為 **optional 輸入 / C4 ego-diagnostic**，非主軸。

## 4. v4 → v5 對照
| 面向 | v4 | v5 |
|---|---|---|
| 主軸 | 不確定性 conditioned on VINS quality（feature concat） | 動態物體狀態 **observability / validity**（幾何可解釋） |
| 核心輸出 | Σ_p, Σ_v（連續不確定性） | **validity levels**（full/position-only/invalid-vel/unobservable/warning）+ OVI |
| VINS quality | 主 conditioning（A2 賭注，失敗） | optional 輸入 / C4 ego-degradation diagnostic（加分） |
| 模型 | black-box MLP error regression | **OVI 幾何可解釋 index** + 輕量 calibration |
| 主貢獻 | A2（VINS-conditioning 贏）→ 未成立 | C1 observability phase map / C2 OVI / C3 refusal policy / C4 diagnostic |
| 證據狀態 | A2 negative/weak | velocity-validity 崩潰、position-only regime、refusal 有效 = **正面支持** |

## 5. 可保留 / 不可宣稱
- **可保留**：raw object benchmark + phase map（measurement，紮實）；refusal policy 降過度自信 velocity（已驗）；velocity 隨幾何不可觀測（強資料證據）；yaw-lever 幾何。
- **不可宣稱**：A2 成功 / VINS-quality conditioning 有用（誠實負/弱結果，保留）；first dynamic-object observability（待文獻定位）；dynamic SLAM / object-aided localization / object factor。

**結論**：v5 的四個貢獻都能用**現有 24-run dataset + benchmark + VINS replay 結果**建出，不需重錄、不碰 backend。v4 的 A2 負結果是 v5 切角轉換的依據，不是浪費。
