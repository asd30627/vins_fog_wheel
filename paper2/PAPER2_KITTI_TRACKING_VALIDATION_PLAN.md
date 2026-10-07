# PAPER2 — KITTI Tracking Real-Sequence Validation PLAN

> 目的（單一）：確認 CARLA dynamic_v3 看到的現象在**真實 driving sequence**是否存在——
> (1) velocity validity 隨距離下降；(2) position validity 比 velocity validity 穩；(3) position-only regime 存在；
> (4) invalid-velocity / refusal policy 是否仍有意義。**不碰 backend、不重錄、不做 G3、不包裝成功。**

## 資產（已確認，2026-06-30）
- KITTI tracking training：21 序列（0000–0020）。
- `label_02`：每物體 frame, track_id, type, bbox2d, **loc3d(x,y,z camera)**, dims, rot_y。
- `calib`：fx=721.54, cx=609.56, cy=172.85；stereo baseline ≈ 0.53 m（由 P2/P3 x-offset）。
- `oxts`：vf（前向速度）, yaw → ego-motion 補償。
- `image_02`(left color), `image_03`(right color)：解壓中。

## 可做 / 不可做（誠實）
**可做（label_02 足夠）：**
- **position validity**：raw 3D（GT bbox + stereo SGBM 深度 + 反投影）vs GT loc3d → pos_err → position_valid。
- **velocity validity**：跨 frame 同 track_id 的 GT loc3d 差分（ego-comp via oxts）= GT 速度；raw 3D 差分（ego-comp）= raw 速度 → speed_err, dir_err → velocity_valid。
- distance bins（0-15/15-30/30m+）、position_only、invalid_velocity、refusal policy。
**不可做 / 須標 caveat：**
- KITTI **無直接 velocity GT** → 由跨 frame GT 位置差分導出（有量化噪聲、受 occlusion/truncation 影響）；標明為 derived。
- 只有 21 序列、真實動態物體較稀（vs CARLA dense）；遮擋/截斷物體多。
- raw 估計用 **GT bbox**（隔離偵測噪聲，純測幾何可觀測性）→ 與 CARLA（YOLO bbox）的 bbox 來源不同，但**深度/速度機制相同**（depth jitter at range）；這讓 KITTI 是「最佳偵測下的幾何 validity」=更強的現象測試。

## 方法
1. 解析 calib（fx, baseline, cx, cy）、label_02（per-frame GT objects）、oxts（vf, yaw）。
2. 每 frame：SGBM disparity（image_02 vs image_03）；對每個 movable GT 物體（非 DontCare，loc z>0）：raw depth = fx·baseline / median-disparity-in-bbox；raw 3D（ground-plane x,z）反投影；pos_err = |raw(x,z) − GT loc(x,z)|；range = GT z。
3. 速度：per track_id 跨相鄰 frame，GT 與 raw 各自 ego-comp（vf 前向 + Δyaw 旋轉）後差分 / dt(0.1s) → speed_err, dir_err。
   - **sanity**：GT-static 物體經 ego-comp 後速度應 ≈0（驗證 ego-comp 正確）。
4. validity labels（**同 CARLA 閾值**：pos≤3m, speed≤3m/s, dir≤45°；可 ablation）。
5. 分距離 bin 聚合；**CARLA vs KITTI 對比**；refusal policy（overconfident-wrong-velocity 是否仍降）。

## 輸出
- `scripts/paper2_kitti_tracking_validity.py`、`PAPER2_KITTI_TRACKING_VALIDITY_RESULTS.md`、`paper2_kitti_validity_dataset.csv`、`figs/fig_v5_kitti_vs_carla_validity.png`。

## 判準（誠實）
- **現象成立** = KITTI 也呈現 velocity_valid 隨距離下降 + velocity«position + position_only 存在。
- **不成立 / 部分** = 照實寫；若 velocity 噪聲過大無法分辨，退回弱驗證（track stability / depth-disparity jitter vs distance）。
