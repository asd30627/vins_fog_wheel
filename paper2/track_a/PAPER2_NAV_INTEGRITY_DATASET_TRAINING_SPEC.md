# Paper-2 — Navigation Integrity Monitoring: Dataset & Training Spec

**Change:** `openspec/changes/navigation-integrity-monitoring/`
**Date:** 2026-07-02
**Status:** Planning document. No experiments run. Companion to the formal `specs/dataset-label-training/spec.md`.

---

## 1. Datasets: physical availability and role

All five real datasets are physically present at `/mnt/sata4t/datasets/`.

| Dataset | Size | Role | Labels producible | Not used for |
|---|---|---|---|---|
| CARLA FW-VIO | 411G | closed-loop, controlled VINS degrade, VINS-noise replay, FOG sim | GT pose, GT obstacle pos/vel, collision/near-miss/mode-oracle | (sim-only until corroborated) |
| nuScenes | 376G | real obstacle-state reliability | position/velocity/full_state valid (real obstacle GT) | stereo-VINS ATE benchmark |
| KITTI Tracking | 12G | real obstacle reliability; optional VO/VINS health | obstacle validity (LiDAR GT); pose (oxts) | — |
| KAIST Urban | 564G | VINS HealthNet real; FOG_COAST feasibility | pose error vs RTK; FOG/wheel/IMU degrade; drift-vs-time | dynamic-obstacle navigation claim (no obstacle GT) |
| EuRoC | 99G | VIO health baseline (non-dynamic real failure) | pose error vs Vicon/Leica | dynamic-obstacle claim |
| Oxford RobotCar | optional | long-term appearance VINS-health generalization | pose vs reference (if feasible) | required path |
| User platform | — | deployment validation, small fallback demo | qualitative + small quantitative | large-scale statistical proof |

## 2. Label producibility matrix (per channel)

| Label | CARLA | nuScenes | KITTI | KAIST | EuRoC |
|---|---|---|---|---|---|
| position_valid / velocity_valid / full_state_valid | ✅ GT | ✅ GT | ✅ LiDAR | ❌ no obj GT | ❌ no obj |
| unsafe_now / unsafe_in_{1,3}s / diverging_soon | ✅ GT pose | proxy only | ✅ oxts | ✅ RTK | ✅ Vicon |
| collision / near_miss / freezing / mission_success / mode_oracle | ✅ closed-loop | ❌ | ❌ | ❌ | ❌ |
| FOG_COAST drift-vs-time | ✅ inject | ❌ | ❌ | ✅ real FOG | ❌ |

Rule: a metric is reported only on a dataset that can produce its label (`dataset-label-training` spec).

## 3. Training curriculum (Stage 1 → 4; modules before integration)

- **Stage 1 — Obstacle ReliabilityNet.** Train on nuScenes + KITTI (+ CARLA supp.). Models: HistGBM/XGBoost/monotone + fixed-window temporal pooling (W=5). Deep sequence models (GRU/TCN/Transformer) are NOT adopted — prior work showed negative ROI. Output: `P_{position,velocity,full_state}_valid`, `OPL`.
- **Stage 2 — VINS HealthNet.** Gated by K0 event-count probe. Train on CARLA replay + KAIST (+ KITTI-raw/EuRoC if feasible). Runtime-only inputs; GT-pose labels. Output: `unsafe_{now,1s,3s}`, `diverging_soon`, `LPL`.
- **Stage 3 — Navigation Risk Supervisor.** Train on CARLA/Gazebo closed-loop with frozen A/B outputs + navigation context. Mandatory rule-based baseline. Output: risk mode, speed scale, fallback permission.
- **Stage 4 — Integrated temporal fusion.** Last; only after 1–3. Multi-task heads (localization integrity + obstacle reliability + navigation risk + mode) over sequence embeddings. Not the first model.

## 4. Pose curriculum (mandatory)

- **P1 — GT / oracle pose.** Teacher policy for clean navigation risk (removes localization noise).
- **P2 — VINS-noise replay.** Inject realistic drift, scale drift, yaw drift, delay, reset, jump from VINS replay logs. Primary scalable training source for degraded localization.
- **P3 — live VINS-in-loop.** Validation only; not the first/primary training source (live VINS is unstable and poor for scalable training).

Navigation is never trained on GT-only nor on live-VINS-only.

## 5. Baselines (per channel/layer)

- Obstacle: distance-gate, bbox-area-gate, confidence-gate, raw-speed-gate, constant-velocity-smoothing-gate, all-conservative.
- VINS health: feature-count threshold, reprojection-residual threshold, outlier-ratio threshold, internal `failureDetection() Bas>2.5`, combined rule-based monitor.
- Closed-loop: original navigation, rule-based-threshold supervisor, all-conservative policy, learned supervisor.

## 6. Metrics (fixed before results)

- Integrity: false-safe (HMI) rate, missed-alert rate, time-to-alert, AUROC, AURC, ECE, risk-at-fixed-coverage, valid-retention-at-fixed-risk, alert-limit-exceed detection.
- Obstacle-specific: F1_invalid, overconfident-wrong-velocity, unsafe-velocity-accepted, TTC false-alarm/missed-risk proxy.
- Closed-loop: collision, near-miss, false-safe, missed-risk, min TTC, freezing time, unnecessary-stop, mission-success, recovery-success.

## 7. Fixed thresholds (frozen before evaluation)

- Obstacle position valid: error ≤ 3 m. Obstacle velocity valid: error ≤ 3 m/s (optionally AND dir_err ≤ 45°). Ego-independent error.
- Localization AL, integrity risk, min event count, FOG drift budget, T_max: `TBD-XX` until grounded (Phases 2/6). Reported parametrically until then.

## 8. Kill criteria (dataset/training-facing)

- K0 too few divergence events → HealthNet descriptive/rule-calibration only.
- K1 obstacle reliability fails on real data → drop as main (in-domain already passes; live risk = cross-dataset without target calibration).
- K2 HealthNet not earlier than rule-based on CARLA + ≥1 real → drop learned VINS claim.
- K3 supervisor no closed-loop safety reduction → ship rule-based layer only.
- K4 FOG_COAST drift escapes budget on real → drop fallback claim.
- K5 CARLA-only success → downgrade venue + narrow scope.
