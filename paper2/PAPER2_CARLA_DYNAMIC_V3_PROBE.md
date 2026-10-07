# PAPER2_CARLA_DYNAMIC_V3_PROBE — Workstream B

> Change: paper2-noue-g0-data-grounding。2026-06-30。**probe 已成功執行**（使用者授權啟動 CARLA server 後）。

## B1 — recorder 小改（僅 GT 欄位）✅
- `/home/ivlab3/fwvio_ws/scripts/collect_carla_v2.py`（fwvio_ws 非 git → 備份 `collect_carla_v2.py.bak_20260630_021455` + diff）。per-instance dict 加 1 行 `type_id=a.type_id`。py_compile 通過。

## B2 — probe 腳本 ✅
- `/home/ivlab3/fwvio_ws/scripts/run_carla_dynamic_v3_probe.sh`（含 CARLA server preflight；不自啟）。

## CARLA server（使用者授權啟動）✅
- 專案既有 recipe（docker，SESSION_NOTES.md:88）：
  `docker run -d --rm --name carla0916 --gpus all --net=host -e NVIDIA_VISIBLE_DEVICES=all -e NVIDIA_DRIVER_CAPABILITIES=all,graphics,utility,compute -w /workspace carlasim/carla:0.9.16 bash CarlaUE4.sh -RenderOffScreen -quality-level=Low -nosound -carla-rpc-port=3000`
- 就緒實測：server 0.9.16，map Town10HD_Opt，port 3000 LISTEN。
- ⚠ **container `carla0916` 目前仍在執行**（佔 GPU）。停止：`docker stop carla0916`。

## B3 — probe 執行 ✅
- `bash run_carla_dynamic_v3_probe.sh` → rc=0。錄到 `/mnt/sata4t/datasets/carla_fwvio/Town10HD__dynamic_v3_probe__run01`。
- 240 frames（60 static + 100 ramp + 80 drive），640×480，npc 15，gentle_turn，cleanup 乾淨（destroyed 22 actors, residual 0）。

## B4 — 輸出檢查 ✅
- `recording_meta.json`：`gt=["ego_pose","per_instance_velocity_pose_bbox","per_instance_id"]`，W640 H480 fov90 baseline0.5。
- aux 檔數：stereo_left/right、depth_left、seg_left、flow_left、gt **各 240**。
- per_instance（frame 200，16 instances）欄位齊全：`speed,vx,vy,vz,x,y,z,yaw,ext,type_id`。
  - 範例：`vehicle.lincoln.mkz_2020` pos(28.6,141.0,-0.0) speed 8.02 ext[2.45,0.92,0.75]；`vehicle.bmw.grandtourer`；`vehicle.tesla.cybertruck`。
  - **type_id（class）成功記錄** → B1 改動驗證有效。

## B5 — seg-instance-id ↔ actor-id 對照 ✅（重要發現）
- 讀 `seg_left/000200.npy`（[...,1] = instance id = G+B*256）unique top：`29652, 36097, 36219, 27147, ...`。
- gt actor ids（frame 200）：`24..39`。
- **DIRECT-EQUAL overlap = 僅 {25}（巧合）** → **seg-instance-id ≠ CARLA actor.id**，確認 `build_labels.py:117` 標的 non-trivial。
- **結論**：物體 ↔ GT 關聯**不能靠 seg-id 相等**，要走 **3D 幾何最近鄰匹配**（back-project → 比對 GT actor 位置/bearing）。raw object pipeline 已採此法（不依賴 seg-id）。

## 不做（需使用者批准）
- ~30 條完整大量錄製（probe-before-bulk gate；probe 已成功，等使用者批准放行）。
