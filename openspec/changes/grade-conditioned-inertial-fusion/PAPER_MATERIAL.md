# PAPER_MATERIAL — information useful for writing the paper

## Material 1 — methodological trade-off argument (for Method / Discussion: shows we considered thoroughly and ruled out the other path before choosing this one)

> We initially explored learned per-feature anisotropic covariance weighting on visual features, but experiments found: (a) 95.7% of the cross-feature variance of that signal is carried by an isotropic magnitude, with the anisotropy near-constant; (b) that magnitude mainly re-encodes geometric constraint strength (Spearman +0.69 with depth, −0.69 with disparity, +0.36 with track length), overlapping the BA triangulation mechanism; (c) physical-anchor investigation showed low-trust features are NOT dynamic objects (spatial clustering ratio ≈ 1.0, unrelated to dynamics) but near-range / high-disparity / short-track geometrically-weak points; (d) a continuous weight is in structural conflict with the robust kernel (Huber delta=1.0) hard threshold — relaxing it yields chaotic non-monotonicity, removing it diverges (a three-way controlled experiment confirmed this). We therefore placed the AI in the inertial fusion layer rather than the visual weighting layer.

## Material 2 — anti-cherry-pick discipline (for Experimental Setup: directly demonstrates rigor, a Q2 plus)

> LOSO held-out (a win number may come only from a fold whose training set excluded that sequence); do-no-harm gate (clean sequences must not reproducibly worsen); cross-grade / cross-sequence direction consistency; tiered reporting (a 0–5% improvement is reported faithfully as below-threshold, not hidden); isolated execution (determinism std ≤ 0.1%); provenance (every number carries onnx md5 + commit + isolation proof).

## Material 3 — FOG-base determinism anchor numbers (already measured; use in the paper)

> FOG-base (wheel-off, isolated, 5-rep): urban35 60.74±0.07 (CV 0.1%), urban31 108.35±0.01, urban36 260.77±0.00. FOG-base is deterministic. (Note: this is wheel-off; wheel-on clean-env determinism is not yet measured — a tasks.md to-do.)

## Material 4 — CARLA grade-setting method (investigated 2026-06-25; confirmed; the concrete answer to the reviewer's second knife)

> Grades are defined by Allan-variance standard parameters (ARW / bias / bias-RW / scale-ppm), 4 discrete grades: ideal / military_fog (0.01°/hr) / industrial_fog (0.3) / precision_mems (5.0), plus a KAIST-alignment point (0.05) and a general-IMU point (~10). Source: `carla_dataset_replay_ros2_imu_grade.py:37-42` PROFILES.

| grade | ARW [deg/√hr] | bias drift [deg/hr] | bias-RW [(deg/hr)/√s] | scale [ppm] |
|---|---|---|---|---|
| ideal_imu | 0 | 0 | 0 | 0 |
| military_fog | 0.003 | 0.01 | 0.0005 | 50 |
| industrial_fog | 0.03 | 0.3 | 0.005 | 200 |
| precision_mems | 0.15 | **5.0** | 0.05 | 1000 |

> ⚠️ Counter-intuitive naming: `precision_mems` is the WORST (5°/hr), NOT navigation-grade. Grades order by bias only: ideal < military < industrial < precision.
> Injection model (per axis, rad/s): `gyro_meas = (1+scale_err)·gyro_clean + const_bias + bias_RW + white_noise`. Gyro only graded; accel kept clean.
> Existing full long-sequence asset: `/mnt/sata4t/datasets/carla_vins/v21_300s_grade_matrix` (37G; 3 cities × 2 weather × 4 grades × 4 seeds; each ~310 s, 6200 stereo @20Hz, 31000 IMU @100Hz, precise GT pose; 120 s / 600 s variants exist).
>
> **Fidelity calibration (the crux): the grade comparison is admitted by a PER-SEGMENT visual-health gate** — a time-window is admissible only if the segment-local `ideal_imu` `est_scale ∈ [0.85, 1.15]`; collapsed segments are dropped, the rest of the sequence is kept; primary on 120 s sequences. The per-segment granularity (not whole-sequence) is deliberate: dynamic scenes (Innovation 3) corrupt vision *locally*, so a whole-sequence gate would starve the dynamic×healthy window. It keeps **local dynamic perturbation** (the signal) and excludes only **scale collapse** (the contamination). It does NOT make pollution degree a second variable (rejected option C). This is the core defence against the reviewer's "what you measured is visual scene collapse, not FOG grade" knife. Evidence base: `V21_300S_GRADE_DIAGNOSIS.md` (grade↔bad_union Spearman 0.705; industrial/precision degradation is often visual scale-collapse; military(0.01) ≈ ideal — no degradation). (TODO: the concrete consistency threshold X% is filled after the calibration runs.)

## Material 5 — three knives and their solutions (pre-submission self-review checklist)

- **Knife 1 — "how is this different from DualProNet / FoGNet?"** → comparison table + fusion-layer / cross-grade / dynamic three-point difference.
- **Knife 2 — "is the CARLA simulation trustworthy?"** → KAIST ground-truth-point calibration + Allan-variance parameters (the crux, the most effort).
- **Knife 3 — "isn't this just parameter tuning?"** → the anti-cherry-pick discipline (material 2).

## Material 6 — CARLA→VINS known root causes + fixes (apply when re-wiring the wheel-WS player; avoid re-stepping)

> ① IMU power-on spike → VINS emits only ~1 row → `--skip-imu-head 150` / drop_spike_50.
> ② Wrong R1 extrinsic (det≈−1) → scale escape 7.5× → use R3 `[[0,0,1],[0,1,0],[-1,0,0]]` (det=+1) → scale 1.02.
> ③ IMU axis handedness (CARLA left-handed vs ROS right-handed; gyro is a pseudovector) → `--variant proper_yref`: accel `(ax,−ay,az)`, gyro `(−wx,wy,−wz)`.
> ④ Old fwvio parquet `sigma_uv=0` / wrong schema → use the new CSV pipeline (`carla_fwvio`), do not reuse the old parquet.

## CARLA start/stop (confirmed command; Docker carlasim/carla:0.9.15)

```
docker rm -f carla0915 2>/dev/null
docker run -d --name carla0915 --gpus all --net=host --ipc=host --user root \
  -e NVIDIA_VISIBLE_DEVICES=all -e NVIDIA_DRIVER_CAPABILITIES=all \
  carlasim/carla:0.9.15 \
  /bin/bash -lc 'su -s /bin/bash carla -c "cd /home/carla && ./CarlaUE4.sh -RenderOffScreen -quality-level=Low -nosound -carla-rpc-port=2000"'
sleep 25; docker ps | grep carla0915; nvidia-smi | grep -E 'CarlaUE4|Unreal'
# When done: docker rm -f carla0915 (no --rm, to avoid leaking the GPU). Confirm `docker ps` shows no carla before measuring any KAIST gate number (isolation rule, Decision 10).
```
