# Design — paper2-observability-aware-object-validity-v5

> v5 = Observability-Aware Dynamic Object State Validity for GPS-Denied Navigation。全用現有資料，不碰 backend。
> 證據基礎見 `PAPER2_V4_TO_V5_EVIDENCE_MAP.md`；文獻定位見 `PAPER2_V5_LITERATURE_POSITIONING.md`。

## 1. 定位（v5 不是什麼 / 是什麼）
**不是**：dynamic SLAM、object-aided localization、object factor backend、detector/tracker 改良、trajectory prediction、generic uncertainty estimation、conformal risk-tube paper、VINS-quality feature concatenation paper。
**是**：> Observability-aware dynamic object state **validity layer** for GPS-denied navigation — 判斷何時可信 object position/velocity、何時應拒絕輸出 velocity。

**輸入**：object observation features（bbox/area/aspect）、range/bearing/bearing-change、depth/disparity quality（med/std）、track age/association stability、ego yaw/pose uncertainty proxy、optional VINS reliability features、density/occlusion proxy。
**輸出**：position_valid、velocity_valid、full_state_valid、position_only、invalid_velocity、unobservable、conservative_warning、**OVI（observability validity index）**、planner-facing state level。

## 2. Contributions

### C1 — Observability/validity phase map
把既有 raw object benchmark（15811 matched）轉成 validity regime 圖（不只 error）：
- distance × density、range × bearing-change、depth-quality × distance、yaw-lever × range、track-age × velocity-error。
- 每 cell 標：full-state observable / velocity-invalid / position-only / conservative-warning（依 validity 比例）。
- 資料已示：velocity validity 0.38/0.16/0.06（近→遠），position validity 0.89/0.73/0.30 → 三段式 regime 由資料浮現。

### C2 — Observability Validity Index (OVI)
**幾何可解釋**（非 black-box）。核心項（runtime-observable）：
- `yaw_lever = range_m · sin(yaw_sigma)`（ego-yaw 不確定性 × 距離 → lateral 物體誤差 lever；yaw_sigma 來自 VINS proxy 或固定先驗）。
- `bearing_change_rate = |bearing_change_deg| / dt`（velocity 可觀測性核心：靜止/同向跟車 bearing 不變 → velocity 不可觀測）。
- `depth_noise_proxy = g(disp_med, disp_std)`（深度抖動；遠距小視差 → 深度/velocity 噪聲大）。
- `velocity_observability_proxy = bearing_change / range`（或 parallax/time）。
- `assoc_stability = f(track_age)`（短 track → 不穩）。
輸出三個 index：`OVI_position`、`OVI_velocity`、`OVI_full_state`（單調組合 + 輕量 isotonic/logistic calibration 對 validity label）。**OVI 必須可解釋、可寫成公式、可 ablation 各項。**

### C3 — Refusal-aware dynamic object state policy
levels：full_state / high_covariance / position_only / velocity_invalid / unobservable / conservative_warning。
由 OVI 門檻決定（門檻寫在 report，可 ablation）。評估：overconfident-wrong-velocity、invalid-velocity recall/precision、valid-velocity retention、planner-usable ratio、position-only/warning ratio、false-refusal rate、risk-coverage、per-distance/density/town。
baseline 對照：no-policy（全輸出 velocity）、v4 NOUE policy、v5 OVI policy、v5 OVI+calibration。

### C4 — Object-consistency ego-degradation diagnostic（optional, 加分）
多物體一致的假 lateral velocity / fake motion pattern → 當 ego pose/yaw 漂移時，遠距物體會出現**一致方向**的假運動。offline diagnostic：
- 每 frame 對多物體的 raw lateral velocity 求一致性（mean/變異）。
- 與 VINS replay 的 scale 發散 / feat_count drop / outlier ratio 相關。
- 看能否當 independent ego-degradation alert。
**限制**：不回饋 VINS、不加 object factor、不宣稱 localization improvement、只做 diagnostic/alert。**弱就標 weak。**

## 3. Validity labels（初版 rule；閾值寫 report、可 ablation）
```
position_valid        = pos_err_m <= 3.0
velocity_valid        = speed_err_ms <= 3.0 AND dir_err_deg <= 45
full_state_valid      = position_valid AND velocity_valid
position_only         = position_valid AND NOT velocity_valid
invalid_velocity      = NOT velocity_valid
unobservable_candidate= invalid_velocity AND (low bearing_change OR far range OR high depth_jitter)
high_risk_object      = invalid_velocity AND near range (近距但 velocity 錯 = 危險)
```
閾值非絕對真理；後續 ablation（2m/3m/5m、dir 30/45/60）。

## 4. 紅線（v5 階段硬約束）
不改 VINS backend；不加 object factor；不做 G3 backend scaffold；不重錄 CARLA（除非明確缺）；不把 v4 A2 說成成功；不刪 v4 結果；不過度 claim "first"（用 "to our knowledge"/"we focus on"/"unlike methods that…"）；不以 conformal risk tube 為主創新；C4 不回饋 VINS、不宣稱 localization improvement。

## 5. 評估指標彙整
- validity 分類：AUROC/F1（velocity_valid、invalid_velocity、unobservable）、false-valid rate、false-refusal rate。
- refusal policy：overconfident-wrong-velocity、invalid-vel recall/precision、planner-usable ratio、risk-coverage、missed-danger（若可）。
- phase map：per distance bin / density / town 的 validity 比例。
- OVI：是否比 distance-only / depth-only / bearing-only 單因子更能抓 invalid-velocity（AUROC 提升）。

## 6. Gates
- V5-G1（phase map + validity labels）：validity regime 由資料浮現、可解釋 → 報告。
- V5-G2（OVI）：OVI 是否勝單因子 baseline（抓 invalid-velocity AUROC）→ 報告。
- V5-G3（refusal policy）：是否降 overconfident-wrong-velocity 且 false-refusal 可控 → 報告。
- V5-G4（optional ego diagnostic）：object-consistency 是否與 VINS 退化相關（promising/weak/null，誠實）。
每 gate STOP-and-report；主題定稿/backend 決策交使用者。

## 7. 風險
- validity 受限於現有 dataset（Town10HD+Town01、velocity 來自 centroid-diff raw 估計）→ 結論標 scope。
- VINS scale 發散 → yaw_sigma proxy 噪聲大；OVI 的 yaw_lever 項用 VINS proxy 時要標 caveat（亦可用固定 yaw 先驗做 ablation）。
- velocity GT 來自 GT actor，raw velocity 來自跨 frame centroid diff（noisy）→ validity label 噪聲，需 robust 閾值 + ablation。
