# PAPER2_RAW_OBJECT_PROBE_RESULTS — Workstream C (Q-A first quantification)

> Change: paper2-noue-g0-data-grounding / paper2-viwo-conditioned-noue-v4 (Phase G0)。2026-06-30。
> **Q-A 從「無法量化」解鎖 → 首次量化。** 用現成零件、real stereo 深度（非 GT 深度）量 raw 物體估計髒度。**這是 G0 首跑 feasibility，非最終 benchmark。**

## 資料來源（provenance）
- Recording：`/mnt/sata4t/datasets/carla_fwvio/Town10HD__dynamic_v3_probe__run01`（dynamic_v3 probe，本 session 錄）。
- 240 frames @20fps，640×480，fov 90，baseline 0.5，npc 15，含 depth/seg/flow GT + per-instance `x,y,z,yaw,ext,type_id,vx,vy,vz`。
- pipeline：`scripts/paper2_raw_object_probe.py`（env `gf`）。指令：
  `conda run -n gf python scripts/paper2_raw_object_probe.py --rec <REC> --out-csv paper2_raw_object_probe_results.csv`
- raw CSV：`paper2_raw_object_probe_results.csv`（338 detections）。
- 偵測 YOLOv8m movable 類，深度 = OpenCV SGBM（**real stereo，非 GT depth** → 量的是真 raw 髒度），ByteTrack association，ego-comp via gt ego_pose。

## 結果表（distance bin，GT-range 分箱，bearing 4° 匹配，122/338 偵測匹配到車前 GT actor）

| distance_bin | n | pos_err_med (m) | pos_err_p95 (m) | spd_err_med (m/s) | spd_err_p95 (m/s) | dir_err_med (°) | dir_err_p95 (°) | yaw1°_lat_med (m) | r·sin1°_med (m) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0-15m | 6 | 1.30 | 2.70 | 2.96 | 3.38 | 23.8 | 101.8 | 0.08 | 0.08 |
| 15-30m | 37 | 2.97 | 3.58 | 3.72 | 11.04 | 5.8 | 90.0 | 0.34 | 0.34 |
| 30m+ | 79 | **8.35** | **45.83** | **38.03** | **410.90** | 13.3 | 176.2 | 1.02 | 1.02 |

## 解讀（只給事實，不下方向結論）
- **raw 位置誤差隨距離單調暴增**：median 1.30 → 2.97 → 8.35m；30m+ 的 p95 達 45.83m。機制 = SGBM 視差量化：60m 處視差 ≈2.7px，±1px → 深度誤差數十 m（與 p95 45.8m 一致）。
- **raw 速度在遠距變不可用**：spd_err median 2.96 → 3.72 → **38.03 m/s**（30m+ p95 410 m/s 為物理不可能值）。GT 車速僅 ~8 m/s → 遠距 centroid-difference 速度被 frame-to-frame 深度抖動主導 = noise，非真運動。**支持 v4 設計把遠物當 high-uncertainty/invalid regime。**
- **yaw 注入確認幾何**：注 1° ego-yaw → 物體 lateral shift = `r·sin(1°)`（yaw1°_lat 與 r·sin1° 完全相等，因同一旋轉；確認 `e_lat≈r·sin(Δψ)` 槓桿）。30m+ median range ~58m → 1° yaw ≈ **1.0m** lateral 物體誤差。

## 誠實 caveats（這是 G0 首跑，非 benchmark）
1. **單一 probe run**（1 town/seed，80 drive frames + static/ramp），小樣本（0-15m 僅 n=6）。非統計級 benchmark。
2. **匹配 = bearing 4° 最近鄰 + 車前 actor**：可能把近距 false-positive 配到同 bearing 的遠 GT actor → 灌大 30m+ p95（median 較穩健）。需後續以多 run + 更嚴匹配復核。
3. **速度方向誤差**為初步（world-frame 速度重建的座標慣例僅以位置匹配間接驗證）；速度大小誤差結論（遠距爆）穩健。
4. seg-instance-id ≠ actor-id（見 probe 報告 B5）→ 關聯走 3D 幾何最近鄰，非 seg-id；本 pipeline 即如此。
5. 用 SGBM real 深度（非 GT depth）→ 量的是部署可得的 raw 髒度（正確）；若想看「理想上界」可改用 depth_left GT 另跑對照。

## 結論（事實）
Q-A 地基**可量化且已量化**：raw 物體狀態在近距堪用、遠距（尤其速度）嚴重退化，且 ego-yaw 誤差以 `r·sin(Δψ)` 槓桿放大遠物位置誤差。這為 NOUE「conditioned-on-VINS-quality 的可信度估計」提供了感知地基證據（遠物/退化時該給高不確定性）。**是否擴大為正式 benchmark（多 run/density）交使用者批准（G0 gate）。**
