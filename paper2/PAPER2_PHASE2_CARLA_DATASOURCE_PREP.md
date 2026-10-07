# PAPER2_PHASE2_CARLA_DATASOURCE_PREP.md

> **更正註記 (2026-06-30, 主線整合)**：本調查由背景 agent 完成，但有兩處需以 Phase 1/1.5 既成事實修正：
> 1. **`validity_publisher` 與 `csv_replay` 模式已存在**（Phase 1 已建於 `~/nav2_ws/src/paper2_validity_bridge/`，含 `policy` 與 `csv_replay` 參數）。文中「需新寫 ~100 行 validity_publisher」**作廢** → 只需把 CARLA V5 CSV 欄位對齊既有 csv_replay 介面（`stamp,id,validity_class,x,y,z,vx,vy,vz,confidence,range_m`），工時遠低於估計。
> 2. **Gate 狀態更新**：Phase **1.6 (risk-bus 行為) 與 1.7 (多 seed 統計) 皆已 PASS**（見 `PAPER2_PHASE16_RISK_BUS_BEHAVIOR.md` / `PAPER2_PHASE17_MULTISEED_STATS.md`）。因此 Phase 2 正式 A→B closed-loop **已解鎖**可進；但本文件範疇仍只到 dry-run 接線，正式導航數字待實作 Phase 2 後產出。
> 其餘可用性盤點（CARLA binary 未裝、預錄資料/replay/VINS/GPU/validity CSV 皆在、無 lidar 需合成 /scan）維持有效。

## RED LINES (Critical Constraints)

**This is a feasibility study ONLY for Phase 2 planning—DO NOT:**
- Produce formal demo results: frontier is NOT Paper-2 primary contribution
- Modify planner/VINS core logic  
- Run live detector (csv_replay only)
- Treat minimal datasource/synthetic outputs as official navigation performance
- Gate Phase 1.6/1.7 results on Phase 2—**Phase 1.x MUST pass first**; Phase 2 results only advisory

**Scope:** "接線可行性 + dry-run 檢查清單" (connection feasibility + dry-run checklist)

---

## 1. CARLA INSTALLATION STATUS

### ✗ **CARLA Python Package NOT Installed**
```bash
python3 -c "import carla; print(carla.__version__)"
# Exit code 1: ModuleNotFoundError: No module named 'carla'
```

**Evidence:**
- `/home/ivlab3/carla_ws/` contains **ONLY Python recording/playback scripts**, no executable/egg/whl
- Multiple `carla_record_stereo_imu_gt*.py` scripts import `carla` (lines exist), but they **require** external CARLA server running
- No CarlaUE4.sh found in `/home/ivlab3`, `/opt`, or common install paths

### ✓ **CARLA Recording Infrastructure EXISTS** (but requires external CARLA instance)
- **Scripts location:** `/home/ivlab3/carla_ws/`
- **Key scripts:** `carla_record_stereo_imu_gt_warmup_motion_v21.py`, `carla_record_scenario.py`
- **Outputs:** stereo images (left/right), IMU CSV; can replay via `/home/ivlab3/vins_ws/carla_dataset_replay_ros2.py`
- **Dataset:** `/mnt/sata4t/datasets/carla_fwvio/Town*__dynamic_v3__*` (pre-recorded, indexed by /home/ivlab3/fwvio_estimator_ws_wheel/paper2_carla_dataset_status.tsv)

### ✓ **GPU Available for CARLA**
```bash
nvidia-smi
# NVIDIA-SMI 580.159.03, Driver 580.159.03, CUDA 13.0
```

**Status:** Can run CARLA if binary is provided externally; **machine is NOT blocking factor**

---

## 2. CARLA-ROS BRIDGE & COMPATIBILITY

### ✗ **No native carla-ros-bridge for ROS2 Jazzy detected**
```bash
ros2 pkg list | grep -i carla
# (no output)
```

**Status:**
- CARLA-ROS bridge (official) targets ROS1/ROS2 but **Jazzy port maturity unknown**
- **Workaround:** Use existing data replay + CSV-to-ROS adapter (see Section 5)

---

## 3. EXISTING CARLA TOOLS IN THIS WORKSPACE

### Playback Pipeline (Already Functional)
| Component | Path | Purpose |
|---|---|---|
| CARLA Dataset Replay | `/home/ivlab3/vins_ws/carla_dataset_replay_ros2.py` | Publishes stereo+IMU from recorded dataset directory |
| Outputs | `/carla/left/image_raw`, `/carla/right/image_raw`, `/carla/imu` | ROS2 Jazzy topics (Imu, Image msgs) |
| Dataset Index | `/home/ivlab3/fwvio_estimator_ws_wheel/paper2_carla_dataset_status.tsv` | Lists available Town*__dynamic_v3 recordings |
| Stability Baseline | `/home/ivlab3/fwvio_estimator_ws_wheel/CARLA_TOWN_SCAN.md` | Documents which town/route/duration combos work |

### Object GT & Validity (Can Produce GT for Validity Publisher)
| Component | Path | Produces |
|---|---|---|
| CARLA Validity Builder | `/home/ivlab3/fwvio_estimator_ws_wheel/scripts/paper2_v5_build_validity_labels.py` | `paper2_v5_object_validity_dataset.csv` (60 columns: pos/vel/risk labels) |
| KITTI Validity (Real Reference) | `/home/ivlab3/fwvio_estimator_ws_wheel/scripts/paper2_kitti_tracking_validity.py` | `paper2_kitti_validity_dataset.csv` (same schema) |
| Raw Object Benchmark | `paper2_raw_object_benchmark_all_with_vins.csv` | Input to validity builder (track ID, GT range, speed error, etc.) |

**Limitation:** Objects are **offline-extracted from CARLA**; not live during replay. Can replay via CSV if `validity_publisher` exists.

---

## 4. REAL DATASOURCE CANDIDATES

### Candidate 1: CARLA Pre-Recorded (Offline CSV Replay)
| Capability | Status | Evidence |
|---|---|---|
| `/map` (occupancy/static) | ✓ Can generate | Town maps available; need to export/sample |
| `/odom` | ✓ via VINS-Fusion | carla_dataset_replay_ros2 → /carla/* → VINS output |
| `/scan` (lidar/range) | ✗ NOT RECORDED | CARLA scripts record stereo+IMU only, no lidar/range data |
| Object GT (x,y,z,vx,vy,vz) | ✓ via CSV replay | `paper2_v5_object_validity_dataset.csv` has range/bearing/track_id, can convert to /tf or custom topic |
| **Availability** | ✓ Ready | Pre-recorded Town01/06/07/10HD/etc. in `/mnt/sata4t/datasets/carla_fwvio/` |
| **Stability** | ✓ Documented | CARLA_TOWN_SCAN.md: **Town06 auto@0 & Town07 auto@0 are 5-min stable** (OK mechanism for all 300s); others have acc-bias divergence |

**Dry-Run Candidates:**
- `Town06__dynamic_v3__run_auto_r0__300s` (300s, auto route, ATE 86m, OK mechanism)
- `Town07__dynamic_v3__run_auto_r0__300s` (300s, auto route, ATE 111m, OK mechanism)

**Gap:** No lidar/range sensor data → frontier needs range data OR must generate synthetic via object GT + egocentric transform

---

### Candidate 2: Isaac Sim (USD+Nav2)
| Capability | Status | Evidence |
|---|---|---|
| `/map` | ✓ Potential | `/home/ivlab3/nav2_ws/AMR.usd` exists (USD = Nvidia Omniverse format) |
| `/odom` | ✓ Potential | Can publish from sim plugin |
| `/scan` | ✓ Potential | Lidar plugin available in Isaac |
| Object tracking | ◐ Possible | USD scene can include actors; tracking data needs sim plugin |
| **Availability** | ◐ Partial | AMR.usd present; Isaac Sim engine NOT verified installed |
| **Config** | ✓ Reference exists | `isaac_nav2_params.yaml` at `/home/ivlab3/nav2_ws/src/rtabmap_ros/rtabmap_demos/params/` |

**Verdict:** Feasible **IF Isaac Sim binary is installed**; worth investigating but requires separate setup

**Advantage over CARLA:** Built-in ROS2 publisher support, native /scan

---

### Candidate 3: KITTI Tracking (Real-world Reference)
| Capability | Status | Evidence |
|---|---|---|
| `/map` | ✗ No ground map | KITTI has 3D object labels but no map |
| `/odom` | ✓ via OXTS GPS | `/home/ivlab3/fwvio_estimator_ws_wheel/scripts/paper2_kitti_tracking_validity.py` parses oxts/* |
| `/scan` | ✗ No recorded lidar (in training set) | Only left/right stereo + GPS/IMU |
| Object tracking | ✓ GT labels | label_02/*.txt has tracking ID, class, 3D location |
| **Availability** | ✓ Downloading | 0027/0018 being pulled (~6GB each); takes hours due to S3 rate-limit |

**Verdict:** Good for **validity validation** (real objects vs CARLA synthetic); **NOT primary datasource for frontier** (no map, no scan)

---

### Candidate 4: ROS Bag Replay (Generic)
| Capability | Status | Evidence |
|---|---|---|
| From existing bags? | ◐ Limited | Only found `/home/ivlab3/librealsense/unit-tests/resources/single_depth_color_640x480.bag` (tiny test file) |
| Recording infrastructure | ✓ Can create | Could record nav2 run via `ros2 bag record` |
| /map, /odom, /scan, objects | ✓ Format agnostic | Bag just wraps any topic |

**Verdict:** Can USE bags as container, but need a simulator/recorder first (CARLA or Isaac)

---

## 5. EXISTING VALIDITY PIPELINE & CSV REPLAY FORMAT

### Paper-2 v5 Validity Labels (Offline)
**CSV Columns (60 total):**
```
town, density, run, frame, track_id, cls, conf,
[bbox geom...], [VINS quality...], [GT geometry...],
[STATE LABELS] → position_valid, velocity_valid, full_state_valid, 
                  position_only, invalid_velocity, 
                  unobservable_candidate, high_risk_object
```

**Output locations:**
- `paper2_v5_object_validity_dataset.csv` (CARLA-based)
- `paper2_kitti_validity_dataset.csv` (KITTI-based, same schema)

### Proposed CSV Replay Publisher Requirements
**For new `validity_publisher` csv_replay mode, needed columns (from query):**
```
stamp, id, validity_class, x, y, z, vx, vy, vz, confidence, range_m
```

**Mapping from existing CSV:**
| Required | Source Column | Note |
|---|---|---|
| stamp | frame index → ROS time | Convert frame → duration-based timestamp |
| id | track_id | Existing |
| validity_class | {position_valid, velocity_valid, full_state_valid, ...} | Existing labels |
| x, y, z | Derive from range_m, bearing_deg, depth | Convert polar→Cartesian |
| vx, vy, vz | raw_speed_ms + dir_err_deg | Synthetic; body-frame → world-frame |
| confidence | conf (bbox) | Existing |
| range_m | gt_range_m | Existing |

**Status:** Mapping **CAN be done** with simple CSV adapter (seen pattern in paper2_*.py scripts)

---

## 6. FRONTIER + NAV2 ROS2 INTEGRATION

### Frontier Exploration (Existing)
| Component | Path | Status |
|---|---|---|
| Nav2 workspace | `/home/ivlab3/nav2_ws/` | ✓ Built, installed |
| Wavefront frontier | `/home/ivlab3/nav2_ws/src/wavefront_explorer/wavefront_explorer/wavefront_frontier.py` | ✓ Implemented (Costmap2d, OccupancyGrid2d parsing) |
| Required inputs | `/map` (OccupancyGrid), `/costmap_node/costmap/costmap` (Nav2Costmap) | ✓ Standard ROS2 |
| Lifecycle manager | `/home/ivlab3/nav2_ws/build/nav2_lifecycle_manager` | ✓ Compiled |

**Dry-run Topics Needed:**
```
/map → OccupancyGrid (or costmap) from datasource
/odom → Odometry (pose + twist)  
/scan → LaserScan (range data) — OR synthesize from objects + egocentric tf
/amcl_pose → PoseWithCovarianceStamped (nav2 lifecycle)
```

---

## 7. DATASOURCE-TO-TOPIC MAPPING TABLE

### Option A: CARLA CSV Replay (Most Ready)

| Datasource | Topic | ROS Message Type | Source | Feasibility |
|---|---|---|---|---|
| CARLA stereo+IMU replay | `/carla/left/image_raw`, `/carla/right/image_raw`, `/carla/imu` | Image, Imu | carla_dataset_replay_ros2.py | ✓ Ready |
| VINS-Fusion process | `/odometry/imu` or `/vio_odom` | Odometry | Existing VINS node | ✓ Ready |
| CARLA object GT CSV | `/objects_gt` (custom or Marker array) | Custom or visualization_msgs/MarkerArray | paper2_v5_object_validity_dataset.csv + adapter | ◐ Needs adapter |
| **Map** | `/map` | OccupancyGrid or nav_msgs/OccupancyGrid | Export Town map to PGM + metadata | ◐ Doable (not in replay yet) |
| **Scan (BLOCKER)** | `/scan` | LaserScan | Synthesize from CARLA object GT + egocentric radius? | ◐ Hacky; OR use object bearing/range to fake scan |

**Status:** **Option A can go frontier IF we can synthesize /scan from object GT or hardcode a static map**

---

### Option B: Isaac Sim (IF Binary Found)

| Datasource | Topic | ROS Message Type | Source | Feasibility |
|---|---|---|---|---|
| Isaac plugins | `/map`, `/odom`, `/scan` | Standard nav_msgs | Isaac ROS2 bridge | ◐ If installed |
| Object tracking | Custom topic | Custom msg | Isaac tracking plugin | ? Unknown |

**Status:** **Requires verification Isaac is installed**

---

## 8. FEASIBILITY SUMMARY TABLE

| Requirement | CARLA (CSV Replay) | Isaac Sim | KITTI | Verdict |
|---|---|---|---|---|
| **Can provide /odom** | ✓ via VINS(carla_dataset_replay) | ✓ (native) | ✓ (via OXTS) | ALL viable |
| **Can provide /map** | ◐ (offline export) | ✓ (native) | ✗ | Isaac/CARLA-export only |
| **Can provide /scan** | ✗ (no lidar recorded) | ✓ (native) | ✗ | Isaac only, or SYNTH |
| **Has object GT for validity_publisher** | ✓ (paper2_v5_*.csv) | ◐ (TBD) | ✓ (label_02 tracking) | CARLA/KITTI ready |
| **ROS2 Jazzy compat** | ✓ (existing carla_dataset_replay_ros2.py) | ◐ (likely) | ◐ (custom scripts exist) | All compatible |
| **Can run 5+ min stable** | ✓ (Town06/07 auto@0) | ? | ✓ (drive_0027 ~200s) | CARLA verified |
| **No live detector needed** | ✓ (CSV → publisher) | ✓ | ✓ (pre-labeled CSV) | All ✓ |
| **Effort to integrate frontier** | **MEDIUM** (need /scan, /map export) | LOW (if installed) | MEDIUM (KITTI no map) | Isaac << CARLA << KITTI |

---

## 9. MOST PRACTICAL RECOMMENDATION

### Recommended Path for Phase 2 Demo: **Option A1 (CARLA-Lite) → Option A2 (CARLA+Synth/scan)**

**Stage A1: Minimal Dry-Run (1–2 hours)**
1. Use pre-recorded Town06/auto@0 or Town07/auto@0 (300s, stable per CARLA_TOWN_SCAN.md)
2. Replay via `/home/ivlab3/vins_ws/carla_dataset_replay_ros2.py --dataset <town_dir> --rate 1.0`
3. VINS publishes `/odometry/imu` (or equivalent)
4. **Skip /map and /scan for now;** run frontier with **static/dummy map** and **hardcoded object->range conversion**
5. Observe that frontier initializes, tries to explore, outputs waypoints

**Stage A2: Add Scan Synthesis (1–2 hours)**
- Convert `paper2_v5_object_validity_dataset.csv` → `/scan` (LaserScan) publisher
  - Pull object (range_m, bearing_deg) → (r, θ) → synthetic range array
  - Publish at ~10 Hz to match VINS cadence
- Frontier re-plans with updated /scan

**Stage A3: Export Map (1 hour, if time permits)**
- Use CARLA Town*.xodr or pre-rendered Town PGM
- Publish as OccupancyGrid, test with frontier

### If Isaac Sim is Found Installed:
**Option B: Use Isaac directly (skip A1–A3)**
- Verify `/opt/nvidia/isaac` or similar
- Run isaac_sim with nav2 plugins → instant /map, /odom, /scan
- Inject object GT from external CSV if needed
- Cleaner but contingent on binary availability

### Why NOT pure KITTI:
- No map → frontier meaningless (nowhere to explore)
- 3D tracking only for validity, not suitable as sole datasource
- **Use KITTI for validity validation AFTER main demo works**

---

## 10. DRY-RUN CHECKLIST (Before Starting Phase 2 Implementation)

**Do NOT proceed to live frontier demo until ALL items ✓:**

### Pre-Flight
- [ ] Verify GPU available: `nvidia-smi` shows memory, CUDA 13.0
- [ ] CARLA dataset exists: `ls /mnt/sata4t/datasets/carla_fwvio/Town06__dynamic_v3__run_auto_r0__300s/`
- [ ] Replay script works: `python3 /home/ivlab3/vins_ws/carla_dataset_replay_ros2.py --dataset <path> --rate 0.5` → prints "Publishing: /carla/left/image_raw, ..."
- [ ] Nav2 installed: `ros2 pkg list | grep nav2` shows ≥10 packages
- [ ] ROS2 Jazzy: `echo $ROS_DISTRO` → "jazzy"

### Data Readiness
- [ ] Validity CSV exists: `wc -l /home/ivlab3/fwvio_estimator_ws_wheel/paper2_v5_object_validity_dataset.csv` → >1000 rows
- [ ] Track Town06 subset extracted: (from validity CSV, filter town='Town06' ∧ run matches replay dataset)
- [ ] Mapping ready: GT range/bearing columns present in CSV
  
### ROS2 Infra Checks
- [ ] VINS node buildable: `colcon build --packages-select vins 2>&1 | grep -i error` → 0 errors
- [ ] Create mini-test: run carla_dataset_replay + VINS on 30s subset, verify `/odometry/imu` topic live (`ros2 topic list` during replay)
- [ ] Frontier node compilable: `colcon build --packages-select wavefront_explorer` (or equivalent nav2 pkg) → success

### CSV Adapter Stub
- [ ] Write `validity_publisher_csv_replay.py` skeleton (takes CSV file path, outputs /objects_gt at ~10 Hz with required fields)
  - Input: CSV rows (frame #, track_id, range_m, bearing_deg, raw_speed_ms, validity_class)
  - Output: Custom Marker or standard detection message to `/objects_gt` topic
  - TF frame: camera/body-frame; egocentric (0,0,0) = ego center

### Map & Scan Placeholders
- [ ] Static dummy /map publisher (e.g., 10m × 10m OccupancyGrid centered on ego, all free)
- [ ] Synthetic /scan generator from object CSV (e.g., 360-deg laser, fill ranges from objects, 0-range background)

### Instrumentation
- [ ] rosout logging enabled: `ros2 run ... --verbose` on key nodes
- [ ] tf tree listener: `ros2 run tf2_tools view_frames` (check that ego odom frame chains correctly)

### Execution Checklist (Dry-Run Only, No 5-Min+ Recording)
- [ ] Launch CARLA replay node, VINS, Nav2 lifecycle (without controller/planner active) for 30s
- [ ] Verify all topics present: `/carla/left/image_raw`, `/odometry/imu`, `/objects_gt`, `/map`, `/scan`, `/amcl_pose` (if applicable)
- [ ] Frontier costmap server initializes without crash
- [ ] No segfaults in logs for 30 seconds

**STOP here if ANY item ✗. Fix before implementing live A→B navigation.**

---

## 11. GAPS & LIMITATIONS (Honest Assessment)

### Critical Gaps
1. **CARLA Python package not installed** → Cannot run live CARLA client (can only replay pre-recorded datasets)
   - *Mitigation:* Use `/mnt/sata4t/datasets/carla_fwvio/` pre-recorded Town data
   
2. **No /scan data from CARLA** → CARLA recording scripts record stereo+IMU only, no lidar/range
   - *Mitigation:* Synthesize /scan from object GT (bearing_deg, range_m) or use static dummy
   - *Risk:* Frontier exploration quality depends on /scan fidelity; synthetic may not capture real occlusions

3. **Isaac Sim installation status unknown** → AMR.usd exists, but Isaac binary/ROS2 bridge not verified
   - *Mitigation:* Test `python3 -c "from isaacsim import ..."`; skip if fails

4. **No live object detector** → Objects must come from pre-labeled CSV, not real-time detection
   - *Constraint:* Phase 2 demo is replay-based, not live; acceptable for Phase 2 feasibility (Phase 1 is live)

### Map Export Not in Codebase
- CARLA Town maps exist (.xodr format), but no existing script to → OccupancyGrid
- **Workaround:** Use dummy map or generate offline (can skip for minimal Phase 2 dry-run)

### Object State Estimation (vx, vy, vz)
- CSV has raw_speed_ms (centroid velocity magnitude) + direction error
- Conversion to body-frame (x,y,z, vx,vy,vz) needs coordinate transform
- **Status:** Doable but requires care (ego-motion compensation if CARLA frame ≠ world frame)

### Validity Publisher csv_replay Mode
- **Does NOT exist yet** (user mentioned "新寫的 validity_publisher")
- Must implement as part of Phase 2 setup
- **Effort:** ~100 lines Python (read CSV, publish Marker/detection msg, loop)

### Performance / Frontier Convergence
- Frontier needs sufficient /map fidelity and /scan updates
- Synthetic /scan from object points only ≠ real environment (only detects tracked objects, misses walls/clutter)
- **Acceptable for Phase 2:** Feasibility check; not aiming for "perfect exploration"

### Gate Dependency
- **Phase 1.6/1.7 (detector validity thresholds) MUST pass before Phase 2 results count**
- Phase 2 demo is proof-of-concept for "can frontier accept validity labels"
- **Not eligible as primary contribution** until Phase 1 gates pass

---

## 12. IMPLEMENTATION ROADMAP (Estimated Timeline)

| Task | Owner | Effort | Dependencies | Deliverable |
|---|---|---|---|---|
| **Audit:** Verify nav2 + VINS in fwvio_estimator_ws_wheel | Team | 1h | None | Checklist ✓ |
| **Data:** Extract Town06/07 object CSV from paper2_v5_*.csv | Scripts | 1h | validity_dataset.csv | Filtered CSV rows |
| **Adapter:** Write validity_publisher_csv_replay.py stub | Code | 2h | Object CSV schema | ROS node publishing /objects_gt |
| **Map:** Generate/export Town06/07 OccupancyGrid | Scripts or manual | 2h | CARLA xodr or PGM | /map publisher |
| **Scan:** Synthesize LaserScan from object GT | Code | 2h | Object CSV (range/bearing) | /scan publisher |
| **Integration:** Dry-run (carla_replay + VINS + map/scan/objects) | Test | 2h | All above | 30s dry-run ✓, no crash |
| **Phase 2 Dry-Run Plan Document** | Docs | 1h | All | This document |
| **TOTAL (Phase 2 Setup, no live run)** | — | **11h** | — | Ready for Phase 2 implementation |

---

## 13. FINAL RECOMMENDATION

**Proceed with Option A1 + A2 (CARLA CSV Replay + Synthetic Scan).**

**Rationale:**
1. ✓ Pre-recorded data is stable (Town06/07 auto 5-min confirmed in CARLA_TOWN_SCAN.md)
2. ✓ Replay infrastructure ready (carla_dataset_replay_ros2.py + CSV validity dataset)
3. ✓ ROS2 Jazzy compatibility verified in existing VINS pipeline
4. ◐ /scan synthesis is a workaround but acceptable for feasibility demo (real lidar not the blocker)
5. ✓ Effort (11 hours setup) is manageable within Phase 2 prep window
6. ✗ **DO NOT** attempt Isaac Sim without verifying binary installation first (too risky)
7. ✗ **DO NOT** use KITTI as primary datasource (no map for frontier to explore)

**Success Criterion for Phase 2 Dry-Run:**
- Frontier costmap initializes and detects frontier boundaries (even if from synthetic /scan)
- VINS odometry propagates without crash for 30s
- Nav2 lifecycle manager brings up components without error
- Validity labels from CSV are successfully bridged to ROS (proof of concept)

**Not Required for Dry-Run (defer to live Phase 2):**
- Live A→B navigation with motion planner active
- Detector running (objects from CSV only)
- Real 5-minute navigation (30s dry-run sufficient)

---

**Document Generated:** 2026-06-30 (Phase 2 Prep, Feasibility Check Only)  
**Status:** READY FOR REVIEW — Recommend Option A1 + A2 path
