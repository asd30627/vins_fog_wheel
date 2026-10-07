# PAPER2 Phase 0 — SENSOR KNOB AUDIT (what is actually controllable)

> Every sensor/robustness knob that exists in THIS repo, with the actual file + variable + flag. No knob
> assumed. Where a level cannot be reached without a code patch, it is marked **NEEDS PATCH**. Audit only —
> no backend changed. Date 2026-07-01.

---

## A. IMU data quality (the injected measurement)

Source: `/home/ivlab3/fwvio_ws/scripts/gen_carla_grade_imu.py` → writes `<seq>/imu_grade_<grade>.csv`.

**Allan-variance grade PROFILES** (name = gyro tier; `arw` deg/√hr, `bias` deg/hr, `brw`, `scale_ppm`):
| grade | arw | bias | brw | scale_ppm | role |
|---|---|---|---|---|---|
| `ideal_imu` | 0.0 | 0.0 | 0.0 | 0 | perfect (current recipe) — negative control |
| `military_fog` | 0.003 | 0.01 | 0.0005 | 50 | high-grade FOG gyro |
| `industrial_fog` | 0.03 | 0.3 | 0.005 | 200 | mid gyro |
| `precision_mems` | 0.15 | 5.0 | 0.05 | 1000 | MEMS (worst) |

Fine knobs: `--gyro-bias-scale`, `--gyro-noise-scale`, `--gyro-rw-scale`, `--seed`.

**CRITICAL LIMITATION — gyro-only.** The injector degrades **gyro only**; **accel is written unchanged
(clean)** (`acc = arr[:,1:4]`, docstring "gyro = injected, accel = unchanged"). So even `precision_mems`
keeps a **perfect accelerometer** → the metric SCALE / translation stays IMU-accel-pinned; only
ROTATION/yaw degrades. **Degrading accel = NEEDS PATCH** to `gen_carla_grade_imu.py` (add accel ARW/bias).
This is the likely reason vision stayed inert in Phase A: with clean accel + marginalization, translation
never needs vision. The rotation channel is the only one the gyro grade can open.

So: IMU knobs controllable now = **1–5 (gyro noise/bias/RW/scale) via grades**; **accel noise/bias =
NEEDS PATCH**; `ideal_imu` can be turned off simply by using a different grade.

## B. Estimator IMU noise model (how much VINS trusts the IMU)

Config `carla_stereo_imu_640_R3_b05_gm.yaml`: `acc_n: 0.1  gyr_n: 0.01  acc_w: 0.001  gyr_w: 0.0001`
(continuous-time noise densities). Fully controllable via YAML (make a config variant). Note: stock
`gyr_n=0.01` already **over-distrusts** the gyro relative to even the `precision_mems` physical level
(≈8.7e-6 rad/√s) — consistent with the prior finding "VIO configs over-distrust gyro ~59×". So the
estimator-trust knob is independent of the data-grade knob and both are available.

## C. FOG factor

- Factor code exists: `FogYawFunctor` (`estimator.cpp:2632`), gated by **`FOG_YAW_ENABLE`** (env or YAML
  `fog_yaw_enable`, default 0). Reference-only mode: `FOG_YAW_REFERENCE_ONLY` / env `REL_FOG_REFERENCE_ONLY`.
  Second FOG path `FOG_FACTOR_ENABLE` (YAML `fog_factor_enable`, default 0).
- FOG noise: `fog_arw_ = 3.49e-6` **hardcoded** in `estimator.h:226` (comment "YAML in F4" — not yet wired).
  Controlling FOG noise level = **NEEDS PATCH** (expose fog_arw_ via env/YAML).
- **FOG is NOT fed by the replay.** The estimator subscribes `/fog/yaw` (`rosNodeTest.cpp:426`,
  `fog_yaw_callback → inputFogYaw`), but the replay player `paper2_carla_stereo_player_masked.py` publishes
  only images + IMU (+ optional wheel) — **it never publishes `/fog/yaw`**. Recordings DO contain
  `<seq>/fog_synth.csv`. → **Using FOG = NEEDS PATCH** (add a `/fog/yaw` publisher to the player that
  streams fog_synth.csv). Also note the rosNode C2 guard refuses wheel-preload + FOG together.

So FOG on/off/noise (knobs 7–10) all **NEED PATCH** before Round 2 can run. Design only this pass.

## D. Wheel factor
`WHEEL_FACTOR_ENABLE` (YAML `wheel_factor_enable`, default 0) + player `--wheel-csv` (run_one does NOT
pass it). **Wheel is OFF by default** — keep it off this round (per instruction). Controllable, unused.

## E. Visual factor weight / admission
`enable_visual_admission = false` by default; `visual_alpha = 1.0` (neutral). The per-detection admission
weight path exists (`applyVisualResidualWeight`, `selectVisualAlpha`) but is OFF. Per-feature
`feat_weight_` (default 1.0) is the TCSV soft-weight slot. Controllable (would need enabling for soft
weighting in Phase 4).

## F. Robust loss / outlier cull (added this program)
- **Huber (visual)**: `REL_VISUAL_ROBUST_LOSS=1/0` (added), also `REL_HUBER_DELTA`. Default = stock Huber(1.0).
- **Backend 3-px hard cull**: `REL_BACKEND_OUTLIER_CULL=1/0` (added). Default = stock (on).
- Frontend `rejectWithF()` is commented out (feature_tracker.cpp:271) — no frontend RANSAC.

## G. Determinism (prerequisite for ALL of the above)
Stock config `multiple_thread:1 + max_solver_time:0.08` = **nondeterministic** (±~15% ATE). Use
**`carla_stereo_imu_640_R3_b05_gm_DET2.yaml`** (`multiple_thread:0, max_solver_time:1000`) — verified
deterministic (V1==V1rep). Every life-gate replay MUST use DET2 (or an equivalent deterministic config)
and run **strictly sequentially** (parallel vins_node → ROS node-name collision corrupts runs).

---

## Controllability summary
| knob | controllable now? | how |
|---|---|---|
| gyro noise / bias / RW / scale | **YES** | `gen_carla_grade_imu --grade` (+ scales) |
| **accel noise / bias** | **NEEDS PATCH** | injector is gyro-only |
| estimator IMU trust (acc_n/gyr_n/…) | YES | YAML variant |
| **FOG on/off** | **NEEDS PATCH** | player must publish `/fog/yaw` |
| **FOG noise level** | **NEEDS PATCH** | expose `fog_arw_` |
| wheel factor | YES (keep OFF) | YAML + player flag |
| visual admission α | YES (currently OFF) | `enable_visual_admission` |
| Huber on/off | YES | `REL_VISUAL_ROBUST_LOSS` |
| 3-px cull on/off | YES | `REL_BACKEND_OUTLIER_CULL` |
| object/dynamic bbox mask | YES | player `--mask-json` (existing) |
| determinism | YES | DET2 config |

**Round 1 (IMU only) can run now** with gyro grades I0/I1/I2. **Round 2 (FOG) is blocked on 2 patches**
(player `/fog/yaw` publisher + `fog_arw_` exposure) and **accel degradation is blocked on 1 patch** — all
flagged for裁示, not applied this pass.
