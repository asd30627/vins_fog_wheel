# CARLA stereo+IMU VINS debug baseline — R3 + proper_yref + skip150

**Verified working baseline** (current build): `carla_stereo_imu_R3_baseline.yaml` (0.2 m baseline)
/ `carla_stereo_imu_R3_b05.yaml` (0.5 m baseline), replayed with `--variant proper_yref --skip-imu-head 150`.

## The four pieces and why each is needed

### skip_imu_head = 150
CARLA emits a **spawn settling transient** in the first ~1 s of IMU after sensor spawn (accel_z goes
9.81 → huge spike → ~0 → ~4 g bounce). Feeding it makes VINS init gravity wrong → only ~1 row of output.
Dropping the first ~150 IMU samples (~1.5 s) clears it → continuous output.

### proper_yref (IMU axis conversion)
CARLA uses a **left-handed** body frame (x-fwd, y-right, z-up); ROS/VINS math is **right-handed**.
Converting requires a single-axis reflection: accel (polar vector) flips the reflected axis;
gyro (axial/pseudovector) flips the **other two** axes. `proper_yref` = accel (ax, −ay, az), gyro (−wx, wy, −wz).
Naïve "flip same axis on both" is wrong for the gyro.

### body_T_cam rotation: use R3, NOT R1
- **R1 (old, WRONG)** = `[[0,0,1],[-1,0,0],[0,-1,0]]` → camera↔IMU extrinsic rotation mismatch → the stereo
  reprojection is inconsistent with the IMU-propagated pose → **sliding-window velocity/scale RUNAWAY**:
  est_scale ≈ 0.179, APE_no-scale ≈ 256 m, speed ratio 0.7 → 7.5× over the run.
- **R3 (correct)** = `[[0,0,1],[0,1,0],[-1,0,0]]` (det +1): opt-x(img right)→body −z, opt-y(img down)→body +y,
  opt-z(fwd)→body +x. → est_scale ≈ **1.02**, APE_no-scale ≈ **29 m**, APE_scale ≈ 29 m, speed ratio ~0.3–1.5
  (no runaway). This is a 90° optical-axis roll relative to R1 — the correct CARLA-camera-optical ↔ IMU mapping.

The problem name is **"camera–IMU extrinsic rotation error → sliding-window velocity/scale runaway"**, NOT a
constant-scale error. Ruled out as causes: IMU input magnitude (a_imu/a_gt ≈ 1.2×), accelerometer bias
(ba_norm ≈ 0), outlier rejection (disabling it changed nothing), stereo baseline (0.2↔0.5 immune under R1).

## Residual
With R3 there is still ~29 m APE / ~67 m z-drift over a 30 s drive — this is **ordinary stereo-VIO drift**
(no loop closure), already metric (est_scale≈1). It is the **next tuning stage** (IMU noise / loop closure /
longer-baseline), NOT the scale runaway.

## Minimal usable pipeline
`current build` + replay `proper_yref` + `skip_imu_head 150` + `carla_stereo_imu_R3_baseline.yaml`
(use `carla_stereo_imu_R3_b05.yaml` when the recording baseline is 0.5 m).
Original configs under `../carla/` are untouched; do not use R1 as the default baseline.
