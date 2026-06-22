## ADDED Requirements

### Requirement: Motion input is raw optical flow + wheel-motion parts (A+), FOG-independent
The covariance network SHALL receive, per feature, the **raw observed optical flow** (`vx_j, vy_j` = `FeaturePerFrame.velocity`, normalized coords) AND the **wheel SE(2) motion parts** (`w_dx, w_dy, w_dtheta`), IN ADDITION to the existing depth (`logZ, disp, inv_disp`) and image-position (`nx, ny`) inputs. The net SHALL **learn the ego-flow subtraction internally** — reconstruct `ego_flow = f(wheel motion, per-feature depth, position)` and subtract it to obtain an effective residual flow — rather than being fed a precomputed residual. The motion input MUST NOT incorporate vg/fog cross-modal signals. The input vector grows 10→15 (the +5: `vx_j, vy_j, w_dx, w_dy, w_dtheta`).

This A+ design is chosen over feeding `velocity − predict()` because that precomputed residual equals the NLL target ÷ dt (circular → IRLS degeneration). All A+ motion inputs are **cov-independent observables**, so they are identical at train (cov off) and deploy (cov on) — no train/deploy skew, no self-reference.

#### Scenario: Net learns ego subtraction from cov-independent parts (non-circular)
- **WHEN** the per-feature inputs are assembled (training-data generation and deploy)
- **THEN** they include raw `vx_j,vy_j` + `w_dx,w_dy,w_dtheta` + existing depth/position, and the net learns to subtract ego flow
- **AND** they do NOT include `velocity − predict()` (= NLL target ÷ dt), so the input is non-circular

#### Scenario: Inputs are cov-independent (no train/deploy skew)
- **WHEN** the same feature is processed at train (cov off) and at deploy (cov on)
- **THEN** every motion-related input (velocity, wheel motion, depth, position) is a cov-independent observable with the identical value in both — no skew, no self-reference

#### Scenario: FOG-independent, with a stated limitation
- **WHEN** the design is reviewed for narrative separation
- **THEN** FOG provides rotation precision inside IMU preintegration only, and the cov motion signal comes solely from visual flow + wheel motion (no vg/fog)
- **AND** the known limitation is recorded: the wheel gives yaw only, so pitch/roll ego rotation is unmodeled (accepted — small on KAIST flat roads; full angular rate would require FOG, which would violate Framework 2)

### Requirement: Motion input is deployable with no new sensors
The system SHALL assemble the A+ inputs at deploy time inside `computeFeatureReliabilityAnisoLearned()` using only quantities already in scope: `FeaturePerFrame.velocity` (`vx_j,vy_j`), the wheel SE(2) preintegration (`wp->dx, wp->dy, wp->dtheta`), and stereo depth `Z = baseline / disp` (already used for `logZ,disp,inv_disp,nx,ny`). No new sensor or external input SHALL be required, and no precomputed residual SHALL be fed (the net learns the subtraction).

#### Scenario: Deploy assembles A+ inputs from in-scope observables
- **WHEN** the estimator runs the per-feature covariance inference per optimization
- **THEN** the 5 new inputs (`vx_j,vy_j,w_dx,w_dy,w_dtheta`) are read directly from `FeaturePerFrame.velocity` and the wheel preintegration already in scope
- **AND** no `velocity − predict()` residual is computed (avoids the target-circularity)

#### Scenario: Train/deploy parity on the motion inputs
- **WHEN** the golden-vector parity test runs (PyTorch reference vs C++ onnxruntime)
- **THEN** the extended 15-dim input vector (including the 5 motion dims) matches within 1e-5

### Requirement: NLL training target is unchanged
Route C SHALL reuse the existing wheel-reference reprojection residual target (`ex_norm`, `ey_norm`) produced by `build_perfeat_window_dataset.py`. No new dynamic/static or object-direction label SHALL be introduced. Adding the motion input is a conditioning change, not a supervision change.

#### Scenario: Supervision reuses the existing residual target
- **WHEN** the covariance net is trained
- **THEN** the loss is the existing Gaussian NLL against `ex_norm`, `ey_norm`
- **AND** no new label column or supervision signal is added

### Requirement: Input vector extension preserves baseline bit-invariance
The network input vector SHALL grow from 10 to 15 dimensions (the +5: `vx_j,vy_j,w_dx,w_dy,w_dtheta`) at both train and deploy. The deploy path SHALL remain environment-gated and default-OFF, such that with the flag OFF the estimator output is bit-identical to the pre-change baseline. The `cov_norm.npz` normalization SHALL absorb the new dimensions.

#### Scenario: Flag-OFF baseline is bit-invariant
- **WHEN** the motion-input deploy flag is OFF
- **THEN** the estimator output (e.g. md5 of the VIO trajectory, row count) is bit-identical to the pre-change baseline

#### Scenario: Normalization handles new dimensions
- **WHEN** the ONNX model is exported with the extended input
- **THEN** `cov_norm.npz` (mu, sd) covers all 15 dimensions without manual edits

### Requirement: KAIST perfeat training data carries a per-feature velocity column (PRE-TASK 1, required)
Before training Route C, the KAIST perfeat training data SHALL be regenerated so each per-feature row includes the `velocity` (and residual-flow) column(s). This pre-task is REQUIRED and SHALL be completed first. The hand-prior inputs (`lp11/lp22/lp21`) SHALL continue to be built from the populated wheel covariance `w_*` columns; the `sigma_uv=0` failure mode SHALL NOT recur.

#### Scenario: Regenerated KAIST perfeat includes velocity
- **WHEN** the KAIST perfeat logging is re-run after the logger change
- **THEN** every per-feature row contains the velocity column(s) needed for the motion input
- **AND** the `w_*` wheel-covariance columns remain populated so `lp11/lp22/lp21` are well-defined

### Requirement: CARLA mechanism validation is deferred and gated (PRE-TASK 2)
CARLA dynamic data regenerated via the wheel-WS perfeat logger SHALL be used only for mechanism validation (verifying the net orients anisotropy to object motion), and SHALL NOT be a training prerequisite. This pre-task SHALL be performed only AFTER Route C has passed the KAIST corruption win gate. The OLD fwvio CARLA parquets SHALL NOT be used (they have `sigma_uv=0` and the wrong schema).

#### Scenario: Mechanism validation runs only after the KAIST win
- **WHEN** Route C has met the do-no-harm gate and the corruption win gate on KAIST
- **THEN** CARLA dynamic data is regenerated via the wheel-WS logger for mechanism validation
- **AND** before that point, no CARLA data is required for Route C training

### Requirement: FOG-base run-to-run variance is measured first (PRE-TASK 0, required)
Before any Route C training, the system SHALL run FOG-base on the corruption trio (urban35-seoul, urban31-gangnam, urban36-seoul) for 5 isolated repetitions and measure the median-ATE run-to-run variance. The measured variance SHALL be used to fix the concrete corruption-win percentage threshold of the corruption win gate. This pre-task depends on nothing in Route C and SHALL be performed first.

#### Scenario: FOG-base variance fixes the win threshold
- **WHEN** PRE-TASK 0 runs FOG-base on the corruption trio (5 isolated reps)
- **THEN** the median-ATE run-to-run variance (distribution / std) is recorded
- **AND** the corruption-win percentage threshold is fixed from that variance before Route C is evaluated

### Requirement: Do-no-harm acceptance gate on clean sequences
On clean sequences, FOG+Route-C ATE SHALL show **no statistically significant degradation** relative to FOG-base, evaluated multi-rep and isolated. Noise-internal fluctuation and accidental improvement are permitted; only statistically significant worsening fails the gate. This gate explicitly prevents repeating the scalar-reliability clean-ATE net loss of 1.073.

#### Scenario: Clean do-no-harm gate
- **WHEN** FOG-base and FOG+Route-C are evaluated on clean sequences (multi-rep, isolated)
- **THEN** there is no statistically significant clean-ATE degradation of Route-C versus FOG-base
- **AND** fluctuation within run-to-run noise, or an accidental improvement, does not fail the gate

### Requirement: Corruption win acceptance gate
On the dynamic-heavy corruption set, the decisive comparison is FOG-base vs FOG+Route-C, payoff measured in the corruption regime. The corruption set SHALL be the KAIST dynamic-heavy trio urban35-seoul, urban31-gangnam, urban36-seoul (ranked most-dynamic by RANSAC-reject + vg-residual). The FOG-base reference is the PRE-TASK 0 measured baseline (deterministic, 5-rep std ≤0.1%): urban35-seoul **60.74 m**, urban31-gangnam **108.35 m**, urban36-seoul **260.77 m**. (urban28 ATE 15.49 from the old WS is a narrative anchor only — baseline health — not a comparison basis.)

**LOCKED win threshold (PRE-TASK 0, layered):**
- **Primary (victory line):** FOG+Route-C SHALL achieve **≥ 5% median ATE reduction** vs FOG-base on the corruption trio, **with all three sequences reducing (consistent direction)** — not one winning while another worsens. 5% is ~50× the 0.1% determinism floor. The bar SHALL NOT be raised to 10% (a strong FOG backbone could yield a real, meaningful 5–8% that 10% would wrongly reject).
- **Tiered reporting (no binary trap):** if the achieved reduction lands in 0–5%, it SHALL be reported faithfully as "X% reproducible reduction, below the 5% threshold" — NOT hidden as a failure. A reproducible improvement that misses the bar is reported as such, not buried.

#### Scenario: Corruption win gate (primary)
- **WHEN** FOG-base and FOG+Route-C are evaluated on the dynamic-heavy trio (multi-rep, isolated)
- **THEN** the gate is met iff the median ATE reduction is ≥ 5% AND all three sequences reduce (consistent direction)

#### Scenario: Reproducible-but-below-threshold is reported honestly
- **WHEN** the achieved reduction is reproducible but lands in 0–5%
- **THEN** it is reported as "X% reproducible reduction, below the 5% threshold", not as a failure and not hidden

### Requirement: Evaluation rigor and anti-cherry-pick discipline
All gated evaluations (PRE-TASK 0, do-no-harm, win) SHALL be multi-rep and isolated and SHALL report median plus run-to-run spread. **FOG-base was measured to be deterministic (PRE-TASK 0: 5-rep std ≤ 0.1%).** Therefore the corruption and do-no-harm gates SHALL report the **reproducible per-sequence ATE Δ + percentage reduction + effect size**, NOT a p-value — a deterministic system has no stochastic variance for a paired test, so the threshold is defined as a **meaningful effect size, not a noise-clearing significance test**. Every ONNX model and every ATE value entering a results table SHALL carry a **provenance chain** (binary md5, commit, data batch). The do-no-harm gate SHALL cover the **full clean set** (urban28-pankyo, urban29-pankyo, urban26-dongtan, urban27-dongtan), not a sampled subset. Once PRE-TASK 0 fixes the win threshold, the threshold and the corruption sequence list SHALL NOT be changed mid-evaluation, and all outcomes (pass / below-threshold / fail) SHALL be reported faithfully.

#### Scenario: Deterministic-honest reporting (no spurious p-values)
- **WHEN** a gate compares FOG-base vs FOG+Route-C
- **THEN** the report gives the reproducible per-sequence ATE Δ + % reduction + effect size, plus the 5-rep spread to evidence determinism
- **AND** it does NOT manufacture a p-value where there is no stochastic variance

#### Scenario: Provenance on every reported number
- **WHEN** an ONNX model or an ATE value enters a results table
- **THEN** it carries a binary md5 + commit + data-batch provenance chain

#### Scenario: Full clean coverage for do-no-harm
- **WHEN** the do-no-harm gate runs
- **THEN** it evaluates all of urban28-pankyo, urban29-pankyo, urban26-dongtan, urban27-dongtan — not a sampled subset

#### Scenario: Locked thresholds and honest reporting
- **WHEN** PRE-TASK 0 has fixed the win threshold and the corruption sequence list
- **THEN** neither is changed mid-evaluation
- **AND** both pass and fail outcomes are reported faithfully

### Requirement: LOSO evaluation — gate numbers come only from held-out folds
Route C SHALL be evaluated leave-one-sequence-out (LOSO): the ATE reported for any gate sequence (win or do-no-harm) SHALL come ONLY from a model whose training set EXCLUDED that sequence. A single all-data model MAY additionally be trained as the **deployment deliverable**, but it SHALL be labeled deployment-only and SHALL NOT be used for any win or do-no-harm claim (it has seen every sequence — using it would be train-on-test leakage). The win-gate number SHALL come exclusively from LOSO held-out folds. Held-out / fixed splits that move dynamic-heavy sequences out of training are NOT used (they would weaken the dynamic→anisotropy signal the net must learn); LOSO keeps the other dynamic sequences in each fold's training set.

#### Scenario: Win number is from a held-out fold
- **WHEN** the win gate reports an ATE on urban35-seoul / urban31-gangnam / urban36-seoul
- **THEN** that number comes from a LOSO fold whose training set excluded that exact sequence

#### Scenario: Deployment model is never a gate claim
- **WHEN** an all-data (deployment) model exists
- **THEN** it is labeled deployment-only
- **AND** it is never used for any win or do-no-harm number

#### Scenario: Mid-dynamic trend datapoint (F-39)
- **WHEN** Route C is evaluated on urban39-pankyo (the single mid-dynamic sequence) via its own held-out LOSO fold
- **THEN** its ATE is reported as an independent dynamic-level **trend datapoint**, NOT a win or do-no-harm claim
- **AND** it serves as evidence for whether the Route-C gain varies monotonically with dynamic level (heavy 35/31/36 → mid 39 → light 28/29/26/27)
