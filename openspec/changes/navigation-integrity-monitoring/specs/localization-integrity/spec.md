## ADDED Requirements

### Requirement: VINS HealthNet predicts localization safety from runtime-only signals

The localization integrity channel (VINS HealthNet) SHALL predict localization safety using only signals observable at runtime from the VINS estimator and its logs, and SHALL NOT consume ground-truth pose at inference time. It SHALL emit `P_vins_unsafe_now`, `P_vins_unsafe_in_1s`, `P_vins_unsafe_in_3s`, `P_diverging_soon`, `P_last_state_trustworthy`, and a localization protection level `LPL`.

Permitted runtime inputs: feature_count, feature survival ratio, reprojection residual statistics, outlier ratio, keyframe rate, solver iteration count, IMU residual proxy, bias-jump proxy (`Bas`/`Bgs` deltas), velocity jump, vision-vs-gyro yaw-rate inconsistency, image blur / low-texture score, dynamic-object feature ratio (when the obstacle channel is available), and reset / tracking-lost flags.

#### Scenario: No ground truth at inference

- **WHEN** VINS HealthNet runs in deployment or live validation
- **THEN** every input SHALL come from the estimator or its runtime logs (e.g., `reliability_features_vins.csv`, VINS replay metrics)
- **AND** no GT pose, GT velocity, or oracle field SHALL be read at inference time

#### Scenario: Predictive horizons are emitted per frame

- **WHEN** a new estimator frame is processed
- **THEN** the channel SHALL emit `P_vins_unsafe_now`, `P_vins_unsafe_in_1s`, `P_vins_unsafe_in_3s`, `P_diverging_soon`, and `LPL` for that frame
- **AND** each probability SHALL be calibrated so it can be thresholded against a target integrity risk

---

### Requirement: Localization labels are derived from GT pose against an alert limit

Training and evaluation labels SHALL be derived from GT pose where available (CARLA, KAIST RTK, EuRoC Vicon/Leica, KITTI oxts). `unsafe_now = 1[pose_error ≥ AL_loc]`; `unsafe_in_1s`/`unsafe_in_3s = 1[unsafe condition occurs within the horizon]`; `diverging_soon = 1[future error slope exceeds a threshold]`; `last_safe_time =` the latest time before an unsafe state where pose error is within the safety bound. Estimator-emitted reset, tracking-lost, and incomplete-trajectory flags SHALL also serve as labels.

#### Scenario: Alert-limit exceedance defines unsafe_now

- **WHEN** the GT-aligned pose error at time t is ≥ `AL_loc`
- **THEN** `unsafe_now(t) = 1`
- **AND** IF `AL_loc` is still `TBD-AL-LOC`, the label SHALL be produced parametrically over a documented AL range and reported as a sensitivity curve, not a single number

#### Scenario: Diverging-soon uses future error slope

- **WHEN** the GT-aligned error slope over the next horizon exceeds the divergence threshold
- **THEN** `diverging_soon(t) = 1`
- **AND** the label SHALL be computed causally for evaluation (the model input at t SHALL NOT include any future-derived feature)

---

### Requirement: The learned monitor must beat rule-based baselines on lead time and false-safe

VINS HealthNet SHALL be compared against rule-based baselines: feature-count threshold, reprojection-residual threshold, outlier-ratio threshold, the VINS internal `failureDetection()` (`Bas > 2.5`) as an alert source, and a combined rule-based monitor. A learned-benefit claim SHALL require the learned monitor to achieve earlier time-to-alert AND lower false-safe rate than the best rule-based baseline on CARLA and at least one real dataset.

#### Scenario: Learned claim requires beating the internal failure detector

- **WHEN** evaluating on a dataset that contains divergence episodes
- **THEN** the learned monitor's TTA and false-safe rate SHALL be reported alongside the `failureDetection() Bas > 2.5` baseline
- **AND** IF the learned monitor does not beat this baseline on both metrics on CARLA + ≥1 real dataset, the learned claim SHALL be dropped (see K2)

---

### Requirement: Localization integrity is gated by an event-count probe (K0)

Before any learned-HealthNet claim, the channel SHALL run an event-count probe that counts distinct alert-limit-exceeded / divergence episodes across available logs (CARLA R7 drift, degraded Town06/07, grade-injected KAIST, EuRoC). If the count is below `TBD-N`, the channel SHALL be downgraded to a descriptive / rule-calibration contribution and SHALL NOT be presented as a learned failure predictor.

#### Scenario: Insufficient events downgrade the claim

- **WHEN** the event-count probe finds fewer than `TBD-N` distinct divergence episodes with statistical independence
- **THEN** VINS HealthNet SHALL be reported as a calibrated rule-monitor / descriptive analysis
- **AND** the paper SHALL NOT claim a learned divergence predictor for the localization channel

#### Scenario: Sufficient events permit training

- **WHEN** the probe finds at least `TBD-N` distinct episodes across ≥2 datasets
- **THEN** training and the K2 comparison proceed
- **AND** the episode inventory (count, source, duration) SHALL be reported for reproducibility
