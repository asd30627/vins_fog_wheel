## ADDED Requirements

### Requirement: AI acts in the inertial fusion layer, never the visual weighting layer (structural lock)
The learned arbitration SHALL act in the **fusion layer** — by conditioning the information weight of the FOG yaw factor / IMU factors (NULL-loss factors) — and SHALL NOT output any weight or covariance on visual features. The visual `ProjectionFactor`s (mono/stereo/marg) and their `HuberLoss(1.0)` robust kernel SHALL NOT be touched. This is a deliberate architectural lock (Anchor 2), motivated by the demonstrated structural conflict between continuous visual-feature weighting and the Huber hard threshold; it is not an empirical preference and SHALL NOT be relaxed.

#### Scenario: Arbitration touches only the inertial side
- **WHEN** the grade-conditioned arbitration adjusts trust between FOG rotation and visual rotation
- **THEN** it does so by changing the FOG/IMU factor information weight (NULL-loss path)
- **AND** it never changes the visual `ProjectionFactor` weights or the Huber kernel, so the code path never touches Huber

#### Scenario: A visual-weighting design is rejected
- **WHEN** any proposed change would have the AI emit a weight or covariance on visual features
- **THEN** it is rejected as violating this spec (Anchor 2), regardless of measured performance

### Requirement: Effect is rotation-only; honest scope statement
The "strengthen FOG = weaken vision" effect SHALL be claimed **only in the rotation dimension** (FOG measures rotation only; translation still relies on vision + IMU). The paper SHALL state this scope explicitly and SHALL NOT claim a direct visual-downweighting effect on translation. The indirect-but-significant position-accuracy improvement (small rotation error amplified over distance is the dominant GPS-denied long-range drift source) MAY be claimed, labelled as an indirect consequence of locking down rotation.

#### Scenario: Scope is stated honestly
- **WHEN** the method's effect on accuracy is reported
- **THEN** the rotation-only mechanism is stated and any translation/position improvement is framed as an indirect consequence of improved rotation
- **AND** no direct visual-downweighting effect on translation is claimed

### Requirement: Official discrete FOG grade list (Allan-variance parameterised)
The study SHALL use a fixed, official set of discrete FOG grades defined by **Allan-variance standard parameters** (ARW, bias, bias random-walk, scale ppm), not ad-hoc noise. The confirmed base set already exists in `carla_dataset_replay_ros2_imu_grade.py` (PROFILES): `ideal_imu` (ARW 0, bias 0, biasRW 0, scale 0), `military_fog` (0.003, 0.01°/hr, 0.0005, 50ppm), `industrial_fog` (0.03, 0.3°/hr, 0.005, 200ppm), `precision_mems` (0.15, 5.0°/hr, 0.05, 1000ppm). The grade ordering is by bias drift only: `ideal < military < industrial < precision` (note: `precision_mems` is the WORST at 5°/hr, not navigation-grade — the name is counter-intuitive). The set SHALL be extended with a **KAIST-alignment point** (bias=0.05°/hr, between ideal and military) and a **general-IMU point** (~10°/hr, worse than precision_mems). The injection model is per-axis (rad/s) `gyro_meas = (1+scale_err)·gyro_clean + const_bias + bias_RW + white_noise`, applied to the gyro only (accel kept clean).

#### Scenario: Grades are Allan-variance defined
- **WHEN** a FOG grade is used in any experiment
- **THEN** it is one of the official list entries defined by (ARW, bias, biasRW, scale-ppm)
- **AND** noise is injected by the confirmed gyro model, not by ad-hoc perturbation

#### Scenario: KAIST-alignment and general-IMU points are present
- **WHEN** the official grade list is finalised
- **THEN** it includes a bias=0.05°/hr point aligned to KAIST and a ~10°/hr general-IMU point, in addition to the four base PROFILES

### Requirement: Grade comparison is admitted by a per-segment visual-health gate (Pit 1 — survival-critical)
The grade-vs-accuracy comparison (Curve 1 and the AI-gain Curve 2) SHALL be computed only on data where the visual front-end is healthy, so that "grade effect" cannot be contaminated by visual scale-collapse. The visual-health gate SHALL be evaluated at the **per-segment (time-window) granularity**, NOT at the whole-sequence granularity: a segment is admissible for grade comparison ONLY IF the `ideal_imu` grade run is healthy **on that segment**, defined as the segment-local `est_scale ∈ [0.85, 1.15]`. A sequence is NOT admitted or rejected as a whole — its admissible segments are kept and its collapsed segments are dropped.

This granularity refinement is required because Innovation 3's core selling point is **dynamic scenes**, and dynamic scenes inherently cause **local** visual corruption; a whole-sequence health gate would discard otherwise-healthy sequences for a local perturbation and could starve the dynamic×healthy data window. Two things MUST be kept distinct: (i) **local dynamic perturbation** (vision locally corrupted but still working, segment scale healthy) is the **signal to study** and SHALL be retained; (ii) **scale collapse** (the segment's `ideal_imu` scale leaves `[0.85, 1.15]`) is the **contamination to exclude** and SHALL be dropped. The per-segment gate keeps (i) and removes (ii).

**Scope guard (do NOT over-reach):** this refinement changes only the *granularity* of the existing health gate (whole-sequence → per-segment). It SHALL NOT introduce "degree of visual pollution" as a second independent variable (that is the rejected option C and would inflate scope). The dynamic level remains the scene condition of Innovation 3, not a regressor. All other locks are unchanged: discrete grade points, rotation-only scope, no touching the visual factors / Huber, Anchor 2.

The primary comparison SHALL use the **120 s sequences** (confirmed 6/6 ideal healthy, minimal collapse); the **300 s sequences** SHALL be used only as a visually-good-subset corroboration. This constraint exists because the project's own `V21_300S_GRADE_DIAGNOSIS.md` shows grade↔bad_union Spearman only 0.705 and industrial/precision degradation is often visual scale-collapse, not IMU grade — the cross-grade conclusion does not hold if this is not isolated.

#### Scenario: Per-segment gate drops collapsed segments, keeps the rest of the sequence
- **WHEN** a sequence is considered for the grade comparison
- **THEN** the visual-health gate is applied per segment using the segment-local `ideal_imu` `est_scale ∈ [0.85, 1.15]`
- **AND** collapsed segments are dropped while the sequence's admissible segments are retained (the sequence is not admitted/rejected as a whole)

#### Scenario: Local dynamic perturbation is retained as signal, not excluded as contamination
- **WHEN** a segment has local dynamic perturbation (vision locally corrupted) but its segment-local `ideal_imu` scale is healthy (`∈ [0.85, 1.15]`)
- **THEN** that segment is retained as part of the dynamic-scene signal under study
- **AND** only segments whose `ideal_imu` scale collapses out of `[0.85, 1.15]` are excluded as contamination

#### Scenario: Granularity change does not add a pollution regressor (no option C)
- **WHEN** the per-segment gate is implemented
- **THEN** it gates admission by segment-local visual health only, and does NOT turn "degree of visual pollution" into a second independent variable
- **AND** discrete grades, rotation-only scope, and the no-touch-visual-factors lock (Anchor 2) remain unchanged

#### Scenario: 120 s primary, 300 s corroboration
- **WHEN** the cross-grade curves are produced
- **THEN** the primary comparison uses the 120 s sequences and the 300 s sequences serve only as a visually-good-subset corroboration
- **AND** the report states that grade differences measured on visually-collapsed segments would conflate visual collapse with FOG grade

### Requirement: Grade injection and wheel data are merged (Pit 2)
The grade-injection capability (currently gyro-only on the 37G `v21_300s_grade_matrix`, no wheel) SHALL be merged with wheel-speed data before grade-conditioned fusion is trained/evaluated: either grade injection is wired into the wheel-carrying pipeline (`carla_fwvio`, CSV with wheel + synth FOG) or wheel is added to the grade matrix. The resulting per-sequence data SHALL carry grade-injected gyro AND wheel together.

#### Scenario: Merged data carries grade + wheel
- **WHEN** a grade-conditioned training/eval sequence is assembled
- **THEN** it contains both the Allan-parameterised grade-injected gyro and the wheel-speed channel
- **AND** the two sources are not split across separate, unmergeable pipelines

### Requirement: CARLA→wheel-WS player/runner re-wire with the four known fixes (Pit 3)
The CARLA-to-estimator path SHALL be re-wired for the wheel-WS (which currently has no player/runner): `carla_stereo_player` → wheel-WS `vins_node` + a CARLA runner. The re-wire SHALL apply the four known `vins_ws` root-cause fixes: (1) `--skip-imu-head 150` (IMU power-on spike otherwise truncates VINS to ~1 row); (2) the R3 extrinsic `[[0,0,1],[0,1,0],[-1,0,0]]` (det=+1; the R1 det≈−1 extrinsic causes 7.5× scale escape); (3) the `proper_yref` axis transform `accel(ax,−ay,az)`, `gyro(−wx,wy,−wz)` (CARLA left-handed vs ROS right-handed, gyro is a pseudovector); (4) do NOT use the old fwvio parquet (`sigma_uv=0` / wrong schema) — use the new CSV pipeline. This task is stop-and-report.

#### Scenario: Re-wired path applies all four fixes
- **WHEN** a CARLA sequence is played into the wheel-WS estimator
- **THEN** the player/runner applies skip-imu-head 150, the R3 (det=+1) extrinsic, and the proper_yref axis transform
- **AND** it sources data from the new CSV pipeline, never the old `sigma_uv=0` parquet

### Requirement: Per-grade baseline determinism is measured first (PRE-TASK, runs first)
Before any AI-fusion training, FOG-base (no AI) SHALL be run per grade on KAIST and CARLA to measure run-to-run variance / determinism, isolated (CARLA off, no concurrent load). The measured FOG-base per-grade ATE and its run-to-run spread SHALL be recorded and used to fix the concrete win-percentage threshold of the win gate. (TODO: concrete per-grade baseline ATE numbers and the locked win-% are filled after this PRE-TASK runs — do not invent.)

#### Scenario: Baseline variance fixes the win threshold
- **WHEN** the per-grade FOG-base PRE-TASK runs (multi-rep, isolated)
- **THEN** the per-grade median ATE and run-to-run spread are recorded with provenance
- **AND** the win-% threshold is fixed from that spread before any AI-fusion evaluation

### Requirement: Do-no-harm acceptance gate per grade
On clean (visually-healthy) sequences, FOG+AI-fusion ATE SHALL show no reproducible degradation relative to FOG-base **at any grade** — the AI fusion must not make any grade's clean sequence reproducibly worse. Evaluated multi-rep and isolated.

#### Scenario: No grade's clean sequence reproducibly worsens
- **WHEN** FOG-base and FOG+AI-fusion are evaluated on the clean set at each grade (multi-rep, isolated)
- **THEN** no grade shows a reproducible clean-ATE degradation
- **AND** fluctuation within run-to-run noise or an accidental improvement does not fail the gate

### Requirement: Win acceptance gate — dynamic-scene gain, direction-consistent across grades
On the dynamic-scene set, FOG+AI-fusion SHALL deliver a reproducible ATE reduction vs FOG-base, and the gain SHALL be **direction-consistent across grades** (it may not improve one grade while worsening another). The decisive comparison is FOG-base vs FOG+AI-fusion at each grade. (TODO: the concrete win-% is locked from the PRE-TASK baseline variance — do not invent; default discipline mirrors the prior change's "meaningful effect size, not a noise-clearing p-value" once determinism is confirmed.)

#### Scenario: Win gate (direction-consistent)
- **WHEN** FOG-base and FOG+AI-fusion are evaluated on the dynamic set across grades (multi-rep, isolated)
- **THEN** the gate is met iff the reduction meets the locked threshold AND the direction of the gain is consistent across the evaluated grades
- **AND** a grade that improves while another grade worsens fails the gate

#### Scenario: Two curves kept distinct
- **WHEN** results are reported across grades
- **THEN** Curve 1 (FOG grade → ATE; hardware; expected monotonic) and Curve 2 (FOG grade → extra AI gain; direction uncertain, itself the finding) are reported separately and not conflated

### Requirement: Tiered reporting (no binary trap)
A reproducible improvement that lands in 0–5% SHALL be reported faithfully as "X% reproducible reduction, below threshold" — never hidden as a failure and never inflated to a pass.

#### Scenario: Below-threshold result is reported honestly
- **WHEN** the achieved reduction is reproducible but below the locked threshold
- **THEN** it is reported as "X% reproducible reduction, below threshold", not as a failure and not hidden

### Requirement: LOSO evaluation — gate numbers come only from held-out folds
The grade-conditioned model SHALL be evaluated leave-one-sequence-out (LOSO): the ATE reported for any gate sequence (win or do-no-harm) SHALL come ONLY from a model whose training set EXCLUDED that sequence. A single all-data model MAY be trained as the deployment deliverable, but it SHALL be labelled deployment-only and SHALL NEVER be used for any win or do-no-harm claim. Held-out folds SHALL also respect the cross-grade structure so that win numbers are not drawn from data the model has seen.

#### Scenario: Win number is from a held-out fold
- **WHEN** the win gate reports an ATE on a dynamic gate sequence
- **THEN** that number comes from a LOSO fold whose training set excluded that exact sequence

#### Scenario: Deployment model is never a gate claim
- **WHEN** an all-data deployment model exists
- **THEN** it is labelled deployment-only and is never used for any win or do-no-harm number

### Requirement: CARLA fidelity calibration gate (hard requirement — blocks the reviewer's second knife)
CARLA SHALL include a grade point corresponding to KAIST 0.05°/hr, and at that point the CARLA VIO behaviour SHALL be shown consistent with the KAIST real behaviour, under a defined consistency threshold (e.g. relative ATE difference < X%). If this calibration is not passed, the cross-grade conclusions SHALL NOT be claimed. CARLA FOG noise SHALL be set with Allan-variance standard parameters (per the official grade list), so that "grade" has physical meaning. (TODO: the concrete consistency threshold X% and the calibration-point numbers are filled after the calibration runs — do not invent.)

#### Scenario: KAIST-aligned point is calibrated
- **WHEN** the CARLA point at bias=0.05°/hr is run
- **THEN** its VIO behaviour is compared to the KAIST real 0.05°/hr behaviour against the defined consistency threshold
- **AND** if the threshold is not met, no cross-grade conclusion is claimed

#### Scenario: Grade noise is physically meaningful
- **WHEN** any CARLA grade is generated
- **THEN** its noise comes from the Allan-variance parameter set, not ad-hoc perturbation

### Requirement: Isolation rule for all gate/baseline numbers (Decision 10, carried over)
Any gate or baseline number SHALL be measured with CARLA off and no concurrent workload. CARLA is started only while running a CARLA VIO sequence and is shut down (`docker rm -f carla0915`; verify `docker ps` shows no carla) before any KAIST gate number is measured. Run-to-run nondeterminism was root-caused to shared-machine resource contention; under full isolation VINS is bit-identical.

#### Scenario: KAIST numbers measured with CARLA down
- **WHEN** a KAIST gate or baseline number is measured
- **THEN** no CARLA container is running and no concurrent heavy load is present
- **AND** the isolation is recorded as part of provenance

### Requirement: Bit-invariant, env-gated deploy (default-OFF)
The AI-fusion deploy path SHALL be environment-gated and default-OFF such that with the flag OFF the estimator output is bit-identical to the pre-change baseline binary. The grade-conditioning input SHALL be assembled only from quantities already in scope on the inertial side; no new sensor SHALL be required for the primary study.

#### Scenario: Flag-OFF baseline is bit-invariant
- **WHEN** the AI-fusion flag is OFF
- **THEN** the estimator output (VIO trajectory md5, row count) is bit-identical to the pre-change baseline, verified under isolation

### Requirement: Evaluation rigor, provenance, and anti-cherry-pick discipline
All gated evaluations SHALL be multi-rep and isolated and SHALL report median plus run-to-run spread. Every model (ONNX md5) and every ATE value entering a results table SHALL carry a provenance chain (binary md5, commit, data batch, isolation proof). Once the PRE-TASK fixes the win threshold and the sequence/grade lists, they SHALL NOT be changed mid-evaluation, and all outcomes (pass / below-threshold / fail) SHALL be reported faithfully. The do-no-harm gate SHALL cover the full clean set, not a sampled subset.

#### Scenario: Provenance on every reported number
- **WHEN** a model or an ATE value enters a results table
- **THEN** it carries an onnx md5 + commit + data-batch + isolation-proof provenance chain

#### Scenario: Locked thresholds and honest reporting
- **WHEN** the PRE-TASK has fixed the win threshold and the sequence/grade lists
- **THEN** neither is changed mid-evaluation
- **AND** pass, below-threshold, and fail outcomes are all reported faithfully
