# Design — paper2-viwo-conditioned-noue-v4

> Source: `viwo_conditioned_noue_spec_v04.md`（使用者 v0.4 設計）。本檔為 OpenSpec 化的完整設計。執行採 G0→G3 gate；G0 細節在 sub-change `paper2-noue-g0-data-grounding`。

## 1. Problem Statement
GPS-denied 都市下 VINS-Fusion/VIWO ego-pose 受退化（低紋理、視覺 outage、IMU/wheel 不一致、yaw drift）。動態物體 3D 位置/速度**不是**單純由 detector/stereo 決定，而被 ego-pose error 污染：
- ego yaw error → 遠物 lateral error `e_lat ≈ r·sin(Δyaw)`（與速度無關，幾何恆等式）。
- stereo depth error 遠距快速暴增。
- centroid-difference velocity 受 timestamp/association/depth-jitter/ego-comp 影響。
- 同向跟車（低視差、低 bearing change）= observability 本身差，非模型不夠大。

真正問題：**給定 VINS/VIWO 定位品質與物體觀測，系統能否學會判斷該物體狀態的可信度、可觀測性、可用度？**

## 2. Non-goals（不主張的創新）
不主張：首次 dynamic object-aided SLAM（VDO/DOT/DynaSLAM II/SLAMMOT 已存在）；首次用 IMU/VINS prior 處理 dynamic landmarks（DynaVINS/IDY-VINS 已存在）；首次估 object uncertainty（Gaussian-YOLO/MonoRUn/3D-MOT cov 已存在）；首次用 wheel 改善 VINS（VIWO 已存在）；發明新 detector/scene-flow/3D-MOT。**不做 long-term trajectory prediction。**

## 3. System Architecture（NOUE = sidecar）
```
stereo(+depth/seg/flow) → object front-end(detector/mask + association + raw geometry)
   → raw object state p_raw,v_raw + object evidence features
VINS-Fusion/optional wheel → localization quality features
   → NOUE(Σ_p, Σ_v, q_obs, u, p_invalid_vel)
   → uncertainty-driven output policy(planner-facing state / partial / invalid / warning)
   → [G3 optional] high-confidence weak object factor back to VINS (disabled ⇒ baseline bit-identical)
```
NOUE 不取代 optimizer/detector/stereo/scene-flow/planner；它學 raw object state 之上的 **reliability layer**。

## 4. NOUE Model
**Inputs**：(A) object 觀測：bbox/mask size/aspect/area-change、distance/depth mean+var、disparity mean+var、flow mag+var、track age/assoc conf、occlusion/truncation proxy、bearing + bearing change、parallax；(B) raw state：p_raw[x,y,z](body)、v_raw(ego-comp)、speed/heading、temporal smoothness、vel mag/dir change；(C) VINS quality：feature/inlier count、outlier ratio、coverage/entropy、avg track len、visual residual proxy、solver time、failure proxy、`gyro_vins_so3_diff_deg`、good/bad depth ratio、(later) parallax/IMU-preint residual/marg residual/wheel consistency。
**Outputs**：`Σ_p`、`Σ_v`、`q_obs`、`u_planner`、`u_feedback`(optional)、`p_invalid_vel`。
**模型**：低容量、可加 monotonic regularization（distance/depth → reliability）。

## 5. H1 排除（明確）
主 NOUE **不輸出** Δposition/Δvelocity。理由：會變 learned object-state estimation 撞 3D-det/scene-flow/3D-MOT；會搶 uncertainty/observability head 的訓練信號；退化樣本上 state-refine loss 與 calibration loss 會衝突。H1 僅作**隔離 ablation**（獨立 checkpoint）。

## 6. Training Targets / Losses
Labels（per object k,t）：`e_p=||p_raw−p_gt||`、`e_v_mag=|‖v_raw‖−‖v_gt‖|`、`e_v_dir=angle(v_raw,v_gt)`、valid_vel（誤差是否低於 planner 門檻）、observability（幾何 bin 或 GT 誤差門檻導出）、utility（是否安全可用/可回饋）。
Losses：Gaussian NLL（p/v 不確定性）、calibration（ECE-like）、invalid-velocity BCE、utility 分類、（需要時）monotonic reg。**不過度優化 RMSE**——成功包含「對不可觀測樣本給高不確定性」。

## 7. Phase map
軸：localization-quality（nominal / yaw 0.5,1,2° / position drift / scale drift / low-feature·high-outlier / high gyro-vision disagreement / optional wheel slip）× object-condition（density / distance 0-15,15-30,30m+ / car-following / lateral crossing / occlusion / low-disparity / high ego-yaw-rate）。
圖：raw vel err vs distance；raw vel err vs injected yaw；calibration ±VINS features；phase map(quality × distance/density)；output-policy confusion matrix；failure-case gallery。

## 8. Output Policy（active behavior）
high q_obs+low Σ_v → full state；medium → full state+high cov；vel 不可靠但 pos 可用 → position-only/bearing-range + invalid-vel flag；不可觀測 → object exists, vel invalid, no feedback；high danger+low conf → conservative warning。localization feedback 僅 G3 optional（只有 high-confidence 進 backend；退化物禁止；disabled ⇒ bit-identical）。

## 9. Gates（生死線）
- **G0 data foundation**：≥1 段 dynamic CARLA 含 stereo+depth/seg+ego_pose+per-object id/class/pos/vel/bbox，≥20s、每 density ≥3 runs；能產 distance bins、raw pos/vel/dir error、yaw injection。hold：只有 velocity GT/只有 clean/只有 detector 無 GT 皆不可訓練。
- **G1 raw-estimator validation**：raw geometry baseline + yaw injection + distance/density bins 的誤差量出且可解釋。
- **A2 生死線（G2 內）**：NOUE-full 在退化 bins 勝過 NOUE-without-VINS-quality（NLL/ECE/ANEES/risk-coverage 至少一項改善且不傷 RMSE，且改善集中在退化 bins）。不成立 → 降級 benchmark/measurement paper。
- **G2 MVP**：phase map 可解釋；NOUE 勝 visual-only（退化 bins）；output policy 降低 overconfident 錯誤速度；H1 維持隔離。
- **G3**：optional VINS feedback，僅 MVP 強時。

## 10. Data Plan
主：CARLA dynamic_v3 重錄（clean-low/mid、dense、low-texture，各 ≥3 runs ≥20s；保留 recording_meta/gt/stereo/depth/seg/(flow)/imu/wheel_synth/fog_synth/prov）。備援：KITTI tracking（image_02/03+calib+label_02+oxts，track_id 連續、3D loc→ego/world，VINS 軌跡須穩）。KAIST：非監督 object 訓練（無 GT），用於 VINS-quality 分布、退化特徵、wheel/FOG/IMU ablation、定性相關。

## 11. Baselines
centroid-difference（raw 幾何雜訊）、distance-only uncertainty（證明非只學距離）、visual/depth/flow-only uncertainty（A2 主對手）、geometry gate（非學習 observability）、NOUE-without-VINS（ablation）、NOUE-full（proposed）、NOUE+H1（隔離 ablation）。DynaVINS/IDY-VINS 等動態剔除法**僅作背景**，不把 "dynamic feature rejection" 說成本研究貢獻。

## 12. Red lines（G0 階段硬約束）
不訓練 NOUE；不改 VINS-Fusion backend；不加 object factor；不開 ~30 條大量錄製；probe 成功後須使用者批准才放行。所有結果附 provenance，不確定寫「無法確認，需要 X」。

## 13. Risks（摘要，全表見 v0.4 §14）
R2 raw velocity 太雜 → 遠物當高不確定/invalid regime，MVP 限 0-30m。R3 無「動態+position GT」資料 → G0 CARLA v3 gate。R5/R6 審稿說 object uncertainty / dynamic SLAM 已存在 → claim 鎖在 localization-quality-conditioned、不以 object-aided localization 為主 claim。R8 CARLA→real domain gap → KITTI 驗證 + KAIST 分布。

## 14. Venue（待投稿前以校內資料庫核對 JCR/SCImago 年度分區）
RA-L/IROS（簡潔機器人應用佳）、IEEE IV、T-IV/T-ITS（高 bar，需強系統驗證）、IEEE Sensors（以 sensor reliability framing 較可達）。
