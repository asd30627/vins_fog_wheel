# Paper-2（動態物體狀態可信度估計 / VIWO-conditioned NOUE）地基調查 Q-A～Q-F

> 純調查報告（2026-06-30）。**未建 OpenSpec、未寫訓練/方法 code、未改 estimator 主流程。**
> 所有結論附 provenance；標明「磁碟實測」與「知識/估計」。方向決策交還使用者，本報告只給事實。

---

## 執行摘要（兩個地基 + 解鎖路徑）

| 地基題 | 狀態 | 一句話 |
|---|---|---|
| **Q-B（conditioning 地基）** | ✅ **穩** | VINS 品質 features 多數現成可取（`reliability_logger.h` ~150 欄，部署即時可得）；待補的 marg/IMU 殘差、parallax、cov proxy 皆中等工程，hook 點已定位。 |
| **Q-A（感知地基）** | ⚠ **目前無法量化（資料+管線缺席，非結果差）** | 沒有「動態物體 + 位置 GT」同時存在的錄製；raw 物體估計前端未組裝。**但解鎖工作量有界**（見下）。 |

**Q-A 兩條解鎖路徑（成本/風險已界定，交使用者選）：**
- **路徑 1 — CARLA 補錄**：v2 recorder 對 NPC 位置/id/bbox **零改動可得**，class 需小改 1 行。需 ~30 條跨 ≥3 towns × 3 密度。風險：seg-instance↔actor-id 映射未解；每-tick wall-clock 需實測。
- **路徑 2 — KITTI tracking**：label/calib/oxts 完整 → GT（3D 位置+track_id+速度）可建；**但** 立體影像未到位（left zip 截斷、right 缺）、無能吃 tracking 佈局的 VINS runner、唯一同平台 raw 跑痕半發散。
- **前端（Q-E）**：raw 物體估計管線零件**大多已就位**（env `gf`：YOLOv8m+weight+現成 wrapper `dyn_phase0.py`、OpenCV SGBM/KLT、ultralytics 內建 ByteTrack、VINS feature_obs parquet 已含 disparity/depth/flow）。RTX 5090 32GB 近乎全空。缺口僅在升級到 instance-mask 分割或獨立 tracker 時。

---

## Q-A：Raw 物體速度/位置誤差（感知地基）

**結論：實證計算在現有資產上做不出來**，卡在兩缺口（皆為資料/管線缺席，非量出很差）。未編造任何誤差數字。

**缺口 1 — 「有動態物體」與「有物體位置 GT」不同時存在**（`/mnt/sata4t/datasets/carla_fwvio/`，90 條 `recording_meta.json` 實測）：
- `Town10HD__dynamic_dense__run01/02`（唯二有 NPC）：per-instance **只有 `speed,vx,vy,vz`**，無位置/bbox/seg/depth，200 frames@20fps=10s，61 instances。
- `clean` 系列 80 條：有 `per_instance_velocity_pose_bbox`+depth+seg，但 `n_npc=0` → per_instance 只剩 ego（實測 `n_instances=1`）。
- 唯一同時有「物體+位置 bbox」的 `Town10HD__dynamic_v2__run01`（prov 6/18, 400 frames, depth+seg 宣告）**目錄已刪，只剩 .prov.json**。
- KITTI tracking 立體影像未到位（見 Q-D）。
- → 距離分 bin 需物體位置 → 有物體的兩條無位置 → **連分 bin 都做不到**。

**缺口 2 — raw 物體估計管線未組裝**：需 `偵測/mask → stereo 深度 → 跨 frame association → centroid 反投影 + ego-motion 補償`。dynamic 錄製無 seg/depth（只有 stereo）；管線零件存在但未接（Q-E）。屬本次禁寫的 method/front-end code。

**已確立（分析式，非本次量出）**：yaw 注入子題 = 幾何恆等式 `物體位置誤差 = d·sin(yaw_err)`，**只依賴 ego-yaw 誤差與距離、與物體速度無關**（[PAPER2_AUDIT_PHASE0.md:27-28](PAPER2_AUDIT_PHASE0.md)）。尚未用真資料 empirically 驗證。

**記憶更正**：「CARLA dynamic 只有速度 GT」對現存 on-disk dynamic 錄製為真；但 v2 recorder 程式碼會錄位置+bbox，缺口是「dynamic+position 同時」從未保留。

---

## Q-B：VINS 定位品質 features 可得性（conditioning 地基）

**結論：強正面。** 來源 [reliability_logger.h](src/VINS-Fusion-ROS2-jazzy/vins/src/estimator/reliability_logger.h)（schema v3，~150 欄/keyframe ~10Hz，player 即時輸出，部署可得），於 [estimator.cpp:4429](src/VINS-Fusion-ROS2-jazzy/vins/src/estimator/estimator.cpp#L4429) 填值；已有 5s-window 聚合版 [reliability_dataset.tsv](kaist_grade_scripts/reliability_dataset.tsv)。⚠ CSV 每 run 覆寫，需帶 CSV-copy 重跑才有完整 per-(seq) 資料。

| Feature | 現可取? | 來源 / 需改 | 難度 |
|---|---|---|---|
| feature_count / outlier_ratio / coverage | ✅ | `tracked_feature_count_*`,`outlier_ratio_last`,`coverage_*`,`feature_entropy_*` | — |
| reprojection residual | ⚠代理 | `vg_flow_res_*`（flow residual 代理）；離線 parquet 有 `anchor_resid_u/v` | 真 BA 殘差=中 |
| track length / solver time / failure proxy | ✅ | `avg_track_length`,`solver_time_ms_last`,`failure_detected_last` | — |
| estimated yaw rate（task 誤列需改）| ✅ | `gyr_z_mean/std` | — |
| velocity / biases | ✅ | `vel_norm`,`ba_norm`,`bg_norm`(+slope) | — |
| gyro–vision 旋轉分歧（bonus）| ✅ | `gyro_vins_so3_diff_deg` | — |
| marginalization prior residual | ❌未log | `last_marginalization_info` 存在（[estimator.cpp:332](src/VINS-Fusion-ROS2-jazzy/vins/src/estimator/estimator.cpp#L332)），有 `DEBUG_DISABLE_MARG_PRIOR` 旁路 | 中 |
| IMU preintegration residual | ❌未log | `pre_integration->evaluate()`（[imu_factor.h:75](src/VINS-Fusion-ROS2-jazzy/vins/src/factor/imu_factor.h#L75)）| 中 |
| parallax 統計 | ❌未log(已算) | `last_average_parallax`（[feature_manager.cpp:179](src/VINS-Fusion-ROS2-jazzy/vins/src/estimator/feature_manager.cpp#L179)）| 小–中 |
| pose covariance proxy | ❌ | 需從 marg Hessian/ceres 取 | 中–大 |

**Wheel features（optional）**：`reliability_features_vins.csv` 無 wheel 欄位（FOG-aided 設定無 wheel factor）。要 wheel residual/slip：(i) 由 `wheel_synth.csv`/`encoder.csv` 離線比對（不改 estimator），或 (ii) 跑 wheel-factor 設定並 log（改 estimator+config，可能改變 VINS 行為）。本工作區 `_wheel` 分支可能已有 wheel factor，待確認。

---

## Q-C：CARLA 物體位置 GT 補錄可行性

**可否補錄：是。** 核心需求零改動，僅 class 一個次要欄位需小改。

- **零改動可得**（[collect_carla_v2.py:316-320](file:///home/ivlab3/fwvio_ws/scripts/collect_carla_v2.py) 已寫）：每 actor world 位置 `x/y/z/yaw`、actor id（dict key）、bbox `ext`。
- **需小改 — class**：gt json 無 class 欄。建議改 line 318-320 加 `type_id=a.type_id`（**1 行**）。走 seg 路線則需解「seg pixel instance id ↔ CARLA actor id」映射——[build_labels.py:117](file:///home/ivlab3/fwvio_ws/scripts/build_labels.py) 已標 non-trivial 且未解（目前用附近 max-speed proxy 繞過，非真 per-object 對應）。
- **錄製設定**（`config/carla_recording.yaml`+v2 預設）：總幀 = static(60)+ramp(100)+frames(400)=**560**；fps 20；NPC `60 if dynamic else 0`（`--npc` 可掃）；1280×720 fov90；baseline 0.5m；full 感測器 = stereo+depth+seg+flow+imu(100Hz)。**`--skip-aux` 不錄 depth/seg/flow** → 要 class（走 seg）絕不能開。
- **落差**：`run_carla_batch.sh:16` 呼叫的是**舊 `collect_carla.py`（非 v2）**，`REQUIRED_GT` 只列 `per_instance_velocity` → 批次腳本與位置-bbox 邏輯未串接，補錄需直接呼叫 v2 或改 batch（不在零改動範圍）。
- **訓練量依據（估計，非結論）**：現有物體-位置樣本 = **0 條**；2×10s 即使有位置，獨立場景數=2 過少。估計起步 ~**30 條跨 ≥3 towns × 3 密度**（`--npc 15/40/60`）。
- **成本**：磁碟 落點 `/mnt/sata4f/datasets/carla_fwvio`（剩 1.3T，carla_fwvio 現佔 195G）；full-aux+60NPC ≈ **~10.3 GB/條**（aux 由 npy 維度算，估計），~30 條 ≈ ~310GB；skip-aux 同規模 ~62GB（但無 class）。時間：每條 ~3000 ticks，**每-tick wall-clock 需實跑計時且需 CARLA server**，無法離線量。
- **需 X 確認**：(1) CARLA seg G/B instance 編碼是否 == GT actor.id（需實跑一條對照）；(2) 每-tick 實際秒數。

---

## Q-D：KITTI tracking 閉環可用性

KITTI tracking 在 `/mnt/sata4t/datasets/kitti/tracking/`，**全為 zip 未解壓**（實測 `ls`+`unzip -t`+`download.log`）：

| 五件套 | 存在? | 大小 | 完整? |
|---|---|---|---|
| `data_tracking_image_2.zip`（left）| ✅ | 5.7G | ❌ **截斷**（EOCD 缺失；download.log 無 DONE；官方 ~12G 知識）|
| `data_tracking_image_3.zip`（right）| ❌ **不存在** | — | ❌ 未下載 |
| `data_tracking_label_2.zip` | ✅ | 2.2M | ✅（21 序列 label_02）|
| `data_tracking_calib.zip` | ✅ | 88K | ✅（train21+test29）|
| `data_tracking_oxts.zip` | ✅ | 8.0M | ✅（train21+test29，30 欄含速度）|

- **label_02 schema（實測）**：17 欄 `frame track_id type trunc occ alpha bbox(x1y1x2y2) dim(hwl) loc(xyz,相機座標) rot_y`。→ 3D 位置✅、track_id✅、跨 frame 對應✅、速度（相鄰 frame 同 track_id loc 差分/dt，dt=0.1s 為慣例）✅。0000.txt：Car243/Van292/Cyclist154/Ped22/DontCare378，15 有效 track。
- **VINS 可跑性**：有 `config/kitti_raw/`、`config/kitti_odom/`（皆 `imu:0` 純 stereo）+ `build/vins/kitti_gps_test`/`kitti_odom_test`。**但 runner 佈局對不上**：GPSTest 要 raw `image_00/01`、OdomTest 要 odom `image_0/1`，tracking 是 `image_02/03` → **現有 runner 不能直接吃 tracking，需寫 reader 或重排佈局**。tracking 從未跑過 VINS（0 痕跡）。唯一 KITTI 跑痕 raw drive0018 **半發散**（z 漂 454m，[PAPER2_AUDIT_PHASE0.md:24-25](PAPER2_AUDIT_PHASE0.md)）。
- **評估**：label/calib/oxts 足以建 GT，但 (a) 立體影像未到位、(b) 無 tracking runner、(c) 同平台 raw 半發散 → **能否跑到合理軌跡需實跑確認，不能假設**。

---

## Q-E：物體前端組件清單

**GPU/env**：1× RTX **5090 32GB**（driver 580.159.03, CUDA 13.0），目前 0% util 近全空。Conda envs：base/carla/diffvio/**gf**/gf312/gf312_gauss/gf_jazzy/hardening_env/lightglue（註：`lightglue` env 其實是 ROS2 jazzy，無 lightglue 套件）。**`gf` 是唯一裝齊前端的 env**（torch 2.7.1+cu128）。

| 組件 | 可用? | 位置/版本 | 缺什麼 |
|---|---|---|---|
| YOLO (ultralytics) | ✅+weight | env `gf`, ultralytics 8.4.82, `kaist_grade_scripts/yolov8m.pt` | 無 seg 變體/yolo11 |
| SAM/SAM2/Detectron2 | ❌ | — | 套件+weight 全缺 |
| mmdetection(2D)/mmdetection3d | ✅裝 | `gf` mmdet3.3.0；`/home/ivlab3/mmdetection3d`(1.3.0)、`v1.4.0/`(1.4.0) | 無 ready 物體 detector checkpoint（現有 .pth 是 GaussianFormer occupancy/fcos3d backbone）|
| LightGlue | ✅+weight | `gf`/`gf_jazzy`, `/home/ivlab3/Lucas_ws/Visual/LightGlue` | sparse 匹配非 dense flow |
| RAFT/SuperGlue | ❌ | — | 缺 |
| OpenCV 光流 (Farneback/PyrLK) | ✅ | `gf` cv2 4.12.0 | 無 contrib(DIS/DeepFlow) |
| OpenCV stereo (SGBM/BM) | ✅ | `gf` cv2 4.12.0 | — |
| VINS 自帶 stereo+KLT | ✅生產中 | `feature_tracker.cpp`；輸出 feature_obs parquet | — |
| ONNX Runtime | ✅ | `gf` onnxruntime-gpu 1.19.2；C++ `third_party/onnxruntime-linux-x64-1.19.2` | 無 stereo/flow onnx |
| tracker (ByteTrack/DeepSORT/OC-SORT/norfair) | ⚠ 僅內建 | ultralytics 內建 BoT-SORT/ByteTrack（`model.track()`）可用 | 獨立套件+`lap`/`filterpy` 全缺 |

- **現成 wrapper**：[kaist_grade_scripts/dyn_phase0.py](kaist_grade_scripts/dyn_phase0.py) — 已寫好的 YOLOv8m wrapper（movable COCO 類過濾、Bayer debayer、最近時戳索引、overlay），Paper-2 偵測前端可直接複用。
- **feature_obs parquet 欄位**：`u,v,disparity,depth,stereo_score,track_age,klt_fb_err,flow_u,flow_v,anchor_resid_u/v,anchor_maha,semantic_class,instance_id,movable_prob` → 已具逐特徵 stereo 深度+KLT 光流+track association。⚠ `semantic_class/instance_id/movable_prob` 是否有非零內容**未驗證**（producer 在 `fwvio/labels/kaist_pseudo.py`/`build_labels.py`），需 X = 開檔讀實際值。
- **一句話**：env `gf` 無需安裝任何套件即可拼出 raw 管線（YOLOv8m 偵測 + SGBM/KLT 深度光流 + 內建 ByteTrack + VINS parquet）。升級 instance-mask 或獨立 tracker 才需補件。

---

## Q-F：競品 code 與 claim 邊界

**on-disk 盤點**：五方法只有 **DynaVINS** 在本機（`/home/ivlab3/DynaVINS` + `/home/ivlab3/dynavins_repro/dynaVINS`，**兩份 byte-identical**，同 commit `0b4f492`，工作樹 clean）；IDY-VINS/VDO-SLAM/DOT-SLAM/DynaSLAM II 磁碟上不存在。

| Method | 本機? | License | ROS/build | build risk | baseline? | claim 撞車 |
|---|---|---|---|---|---|---|
| **DynaVINS** | 是×2 | GPLv3(實測) | ROS1 catkin, Melodic, Ceres1.14, OpenCV3.4.1(實測) | **高**（ROS1→jazzy 不相容；無 Ceres pin）| 勉強（須 ROS1 docker 或移植；有 IMU 最近 backbone）| 不直接撞——robust BA+feature weight 剔除動態特徵保護 ego（code 實測），與「估物體可信度」相反目標 |
| IDY-VINS | 否 | 知識:推定GPLv3 | 推定 ROS1+IMU | 推定高(未驗證) | 勉強(須先 clone) | 不直接撞（動態剔除護 ego）|
| VDO-SLAM | 否 | 知識:GPLv3 | 知識:無 IMU | 無法確認 | 勉強/否 | **部分撞**——估動態物 SE(3) 軌跡；但給點估計、不 condition 不確定性 |
| DOT-SLAM | 否 | 無法確認 | 知識:語意動態分割 | 無法確認 | 否/勉強 | 不直接撞（與本研究方向一語意剔除重疊，MEMORY 已記 Phase0 負結果）|
| DynaSLAM II | 否 | 知識:GPLv3 | 知識:ORB-SLAM2 base 無 VINS | 無法確認 | 勉強/否 | **部分撞**——聯合追蹤 camera+object 6DoF/速度；不輸出條件式不確定性 |

**claim 邊界結論**：DynaVINS/IDY-VINS/DOT-SLAM = 「剔除動態特徵護 ego」→ 與本研究**不直接競爭**，宜作動機/背景引用。VDO-SLAM/DynaSLAM II = 「估動態物體狀態」→ **部分撞車**，但都不做「不確定性 conditioned on VINS 定位品質」=本研究差異化賣點，宜作物體狀態 baseline。

---

## 交使用者裁示的開放項（design checkpoint 前）

1. **Q-A 解鎖走哪條**：CARLA 補錄（控制度高、需 ~30 條+解 seg-id 映射+CARLA 起來）vs KITTI tracking（真資料、GT 現成，但須補下載 image_2/3 + 寫 tracking reader + 風險半發散）vs 兩者都做。
2. **是否先用 env `gf` 既有零件（YOLOv8m+SGBM+ByteTrack+VINS parquet）組一個最小 raw 物體估計管線**來實證 Q-A（這是本次禁寫的 method code，需你開綠燈）。
3. **Q-B 待補 features 是否值得做**（marg/IMU 殘差、parallax、cov proxy 中等工程）——或先用現成 ~40 features 啟動 NOUE conditioning。
4. 競品：是否要把 DynaVINS 在 ROS1 docker 跑起來當對照，或僅作背景引用。

**未自行下「方向可不可行」結論。已 STOP，等 design checkpoint 決策。**
