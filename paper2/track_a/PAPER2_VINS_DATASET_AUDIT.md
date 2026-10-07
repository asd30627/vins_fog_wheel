# PAPER2 Part 2 / Phase A — VINS/VIO DATASET & PIPELINE AUDIT

> Goal: decide what we can actually run for "does validity/refusal improve VINS/VIO localization".
> Hard conditions honored: CARLA container stays OFF (pure recorded-file replay); offline data only;
> no wheel, no FOG (this phase); no GT feature into VINS (GT only for evaluation / oracle).
> Date 2026-07-01. Every claim below verified by inspecting files on disk.

---

## 1. CARLA offline `dynamic_v3` recordings

Path: `/mnt/sata4t/datasets/carla_fwvio/Town0{1,6,7,10HD}__dynamic_v3__run*` (4 towns, 24 runs each town family).

| component | present? | detail |
|---|---|---|
| stereo left  | ✅ | `stereo_left/*.png` 640×480, 20 fps, 720 frames (~36 s after settle) |
| stereo right | ✅ | `stereo_right/*.png` baseline **0.5 m** (`recording_meta.json`) |
| depth left   | ✅ | `depth_left/` (GT depth — for labels/oracle only, NOT a VINS input) |
| seg left     | ✅ | `seg_left/` semantic seg (usable for dynamic-object masking in Phase C) |
| flow left    | ✅ | `flow_left/` |
| IMU          | ✅ | `imu.csv` ts_ns,ax..gz — **100 Hz** (3601 rows / 36 s), much higher than 20 fps frames |
| calibration  | ✅ | `recording_meta.json`: W,H,fov=90, baseline, cam/imu extrinsics; cam yaml in repo config |
| GT ego traj  | ✅ | per-frame `gt/*.json` → `ego_pose{x,y,z,roll,pitch,yaw}`, `ego_speed` |
| GT objects   | ✅ | `per_instance{id→ speed,vx,vy,vz,x,y,z,yaw,ext,type_id}` (object pos+vel GT) |
| object dets  | ✅ | `outputs/paper2_perdet/Town*__dynamic_v3__run*.csv` (YOLO+depth raw estimate + matched GT) |
| VINS input format | ✅ | replay player consumes the recording dir directly (`carla_stereo_player.py`) |

**Verdict CARLA: TRUE stereo-VIO.** 100 Hz IMU + 20 fps stereo + high-rate IMU preintegration ⇒
tight stereo-inertial is valid. GT ego trajectory enables ATE; GT object pos/vel enable an oracle
dynamic/static routing upper bound. This is the primary Part-2 dataset.

---

## 2. KITTI tracking / raw

KITTI tracking: `/mnt/sata4t/datasets/kitti/tracking/training/{image_02,image_03,calib,label_02,oxts}`.

| component | present? | detail |
|---|---|---|
| stereo L/R | ✅ | image_02 (left) + image_03 (right), both unzipped |
| calib | ✅ | P0..P3 (stereo proj, baseline ≈ 0.54 m), R_rect, Tr_velo_cam, Tr_imu_velo |
| object labels | ✅ | label_02 (2D+3D tracks) — for object validity labels |
| IMU / OXTS | ⚠️ | `oxts/*.txt` is **one row per image frame = 10 Hz** (154 rows / 154 frames in seq 0000) |

**Verdict KITTI tracking: STEREO VO only (NOT tight VIO).** OXTS is at frame rate (10 Hz), far too
sparse for IMU preintegration between keyframes. Honest label = **stereo visual odometry**.
KITTI *raw* has 100 Hz IMU but is **not aligned to the tracking sequences/labels** we use for object
validity, so converting it is a separate effort (flagged, not done tonight). ⇒ For Part 2 VIO we use
**CARLA (true VIO)** as primary; KITTI is reserved as a future **stereo-VO** cross-check, clearly
labeled as VO, not VIO.

---

## 3. Repo VINS pipeline (verified runnable, offline)

| piece | path | note |
|---|---|---|
| VINS binary | `install/vins/lib/vins/vins_node` | built from `src/VINS-Fusion-ROS2-jazzy/vins` (ROS2 Jazzy) |
| stereo+imu config | `src/VINS-Fusion-ROS2-jazzy/config/carla/carla_stereo_imu_1280.yaml` (+640 variants) | output_path rewritten per-run |
| cam intrinsics | `config/carla/cam0_pinhole*.yaml`, `cam1_pinhole*.yaml` | 640 + 1280 variants |
| replay player | `/home/ivlab3/fwvio_ws/scripts/carla_stereo_player.py` | publishes stereo+IMU over ROS2 at `--rate`; **no CARLA service needed** |
| runner | `fwvio_ws/scripts/run_carla_grade_vins.sh <rec> <grade> <tag> [rate] [wheel] [drop]` | launches vins_node + player, writes `vio.csv` |
| ATE gate | `fwvio_ws/scripts/carla_gate.py <rec> <result_dir> <label>` | Umeyama SE(3) ATE (mean), early/late scale ratio, failure count, path-length ratio |
| reliability dump | written by vins_node | `reliability_features_vins.csv` (per-update VINS quality) |

**Trajectory output** `vio.csv`: `ts, px,py,pz, qw,qx,qy,qz, vx,vy,vz` (11 cols).
**Prior evidence it works**: existing `results/paper2_vins/rep_*_Town01/` runs (Town01, rate 0.5) produced
valid `vio.csv` (268 rows) + reliability CSVs. So the pipeline is known-good on Town01.

**Replay cost**: pure-file replay at `rate≈0.2` (intentionally slow to avoid the single-thread VINS lag
bug — see memory `vins-replay-stop-carla`). ⇒ ~36 s clip × 1/0.2 ≈ **~3 min per run** plus VINS warm-up.
Budgeting: a baseline sweep of ~6–8 dynamic-heavy runs ≈ 20–30 min; each Phase-C variant repeats that.

---

## 4. What we can and cannot do tonight (honest)

| capability | status |
|---|---|
| true stereo-VIO on CARLA, offline, CARLA off | ✅ feasible (pipeline known-good on Town01) |
| ATE / scale / failure-count metric | ✅ `carla_gate.py` (extendable to RPE/RMSE) |
| baseline VINS on dynamic-heavy CARLA runs | ✅ Phase B target |
| dynamic-object **input masking** (player-side, no backend touch) | ✅ cleanest intervention; suppress features inside dynamic bboxes/seg |
| validity-aware masking (suppress only model-invalid objects) | ✅ Phase C target (frozen validity → which bboxes to mask) |
| oracle dynamic/static routing (GT) | ✅ upper bound (GT only) |
| soft factor weighting / covariance scaling | ⚠️ needs VINS backend edit; attempt only if input-masking shows signal & time permits |
| learning-through-BA / differentiable BA | ❌ not attempted (repo BA not differentiable; gated by user: don't force it) |
| KITTI **VIO** | ❌ oxts too sparse → only stereo-VO possible (future) |

**Phase B/C plan**: baseline → all-dynamic-mask (DynaVINS-style proxy) → validity-aware mask →
oracle mask, all via the player (no backend change first), on a fixed set of dynamic-heavy CARLA runs.
Metrics: ATE_se3, scale early/late, failure count, #features, (RPE added to the gate). Report all,
good or bad; if masking gives no improvement, analyze why (frontend already rejects outliers / too few
dynamic features / clean dataset / association error) per the user's failure checklist.
