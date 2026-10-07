## ADDED Requirements

### Requirement: Novelty is VINS/VIWO localization-quality-conditioned object-state reliability
The contribution SHALL be framed as estimating dynamic-object state reliability **conditioned on VINS/VIWO localization quality**, a complementary dimension to existing sensing-evidence-conditioned object uncertainty. The paper SHALL NOT claim to be the first dynamic object-aided SLAM, the first to use IMU/VINS priors on dynamic landmarks, the first to estimate object uncertainty, or to do long-term trajectory prediction.

#### Scenario: Claim stays within the localization-quality conditioning dimension
- **WHEN** the contribution is stated
- **THEN** it is "how VINS/VIWO localization quality affects dynamic object state reliability in GPS-denied navigation"
- **AND** dynamic-SLAM, generic object-uncertainty, and trajectory-prediction framings are explicitly listed as non-goals

#### Scenario: A reviewer-collision claim is rejected
- **WHEN** a draft would claim "first object-aided SLAM" or "first object uncertainty"
- **THEN** it is rejected and rephrased as the localization-quality-conditioned reliability claim

### Requirement: Two independent pillars (phase map + NOUE)
The work SHALL stand on two pillars so its value does not hinge on one hypothesis: Pillar 1 = a localization-quality × dynamic-condition × distance **phase map / benchmark** (measurement contribution), and Pillar 2 = the **NOUE method** (uncertainty/observability/utility, conditioned on VINS quality). Pillar 1 SHALL remain a valid contribution even if the NOUE A2 ablation is not significant.

#### Scenario: NOUE A2 fails but Pillar 1 holds
- **WHEN** the A2 ablation does not show VINS-quality conditioning gain
- **THEN** the paper downgrades from method paper to benchmark/measurement paper
- **AND** the phase map / benchmark contribution is still reported

### Requirement: NOUE is a sidecar — it never replaces the optimizer, detector, or planner
NOUE SHALL learn a reliability layer over raw object-state estimates and SHALL NOT replace the VINS-Fusion optimizer, the object detector, stereo depth, scene flow, or the planner. Its inputs are object-observation features, raw object state, and VINS reliability features; its outputs are `Σ_p`, `Σ_v`, observability score `q_obs`, utility score `u`, and invalid-velocity probability `p_invalid_vel`.

#### Scenario: NOUE outputs the reliability layer only
- **WHEN** NOUE runs
- **THEN** it emits position/velocity uncertainty, observability, utility, and invalid-velocity probability over existing raw estimates
- **AND** it does not modify or replace the detector / optimizer / planner

### Requirement: H1 state-residual refine is excluded from the main model
The main NOUE SHALL NOT output Δposition / Δvelocity (learned state correction). H1 SHALL exist ONLY as an isolated ablation with a separate checkpoint, so it cannot steal training signal from the uncertainty/observability heads and cannot collide with 3D-detection / scene-flow / 3D-MOT framing.

#### Scenario: H1 kept isolated
- **WHEN** state-residual refine is evaluated
- **THEN** it runs as a separate ablation model/checkpoint
- **AND** the main NOUE model continues to output only the reliability layer

### Requirement: A2 is the make-or-break experiment
The A2 ablation SHALL test that NOUE-full (with VINS quality features) outperforms NOUE-without-VINS-quality **in localization-degraded bins** on at least one calibration metric (NLL, ECE, ANEES, or risk-coverage) without hurting RMSE, with the improvement concentrated in degraded bins rather than averaged over easy cases.

#### Scenario: A2 gain must be in degraded bins
- **WHEN** A2 is evaluated
- **THEN** the VINS-quality gain is reported per localization-quality bin
- **AND** a gain that exists only in easy/averaged cases does NOT count as A2 passing

### Requirement: Phase map and uncertainty-driven output policy are required deliverables
The work SHALL produce a phase map over a localization-quality axis (nominal, injected yaw 0.5/1/2°, position/scale drift, low-feature/high-outlier, gyro-vision disagreement, optional wheel slip) and a dynamic/object axis (density, distance bins 0-15/15-30/30m+, car-following, lateral crossing, occlusion, low-disparity, high ego-yaw-rate); and an uncertainty-driven output policy with levels full-state / high-covariance / position-only / invalid-velocity / conservative-warning.

#### Scenario: Output policy degrades gracefully
- **WHEN** velocity is unreliable but position is usable
- **THEN** the policy outputs position-only (or bearing/range) with a velocity-invalid flag
- **AND** for unobservable/degenerate objects it outputs "object exists, velocity invalid, no feedback"

### Requirement: Evaluation uses distance bins, density bins, and calibration + risk metrics
Evaluation SHALL report over distance bins 0-15m / 15-30m / 30m+ and NPC density sparse/medium/dense, with raw-state metrics (position/velocity-magnitude/velocity-direction error) and uncertainty metrics (NLL, ECE, ANEES, coverage, overconfidence rate, risk-coverage), plus do-no-harm where a backend path exists.

#### Scenario: Metrics are binned, not just averaged
- **WHEN** results are reported
- **THEN** errors and calibration are broken down by distance bin and density
- **AND** raw-state error and uncertainty-calibration are both reported

### Requirement: Data plan — CARLA dynamic_v3 primary, KITTI tracking validation, KAIST conditioning
The primary supervised dataset SHALL be CARLA dynamic_v3 re-recording with full object-state GT (id/class/position/velocity/bbox + depth + seg + stereo + ego_pose, ≥20s, ≥3 runs per density). KITTI tracking SHALL be used only as real-world validation when downloaded and VINS trajectory is stable. KAIST SHALL be used for VINS-quality feature distribution and degradation characterization, not supervised object-state training (no object GT).

#### Scenario: KAIST is not used for supervised object training
- **WHEN** training NOUE
- **THEN** supervised object-state labels come from CARLA (or KITTI tracking)
- **AND** KAIST is used only for VINS-quality distribution / degradation / wheel-FOG-IMU ablation / qualitative correlation

### Requirement: Wheel claim is conditioning-only, not ATE improvement
Wheel/VIWO SHALL be optional and SHALL NOT be claimed as "wheel improves ATE". It MAY be claimed as providing independent ego-motion / scale-consistency features for reliability conditioning.

#### Scenario: Wheel framed as a conditioning feature
- **WHEN** wheel is used
- **THEN** it contributes ego-motion/scale-consistency features to NOUE conditioning
- **AND** no "wheel improves localization accuracy" claim is made in the primary study

### Requirement: G0 red lines — no training, no backend change, no object factor, no bulk recording
During Phase G0, the work SHALL NOT train the NOUE model, SHALL NOT modify the VINS-Fusion estimator backend, SHALL NOT add any object factor, and SHALL NOT start a bulk (~30 run) CARLA recording campaign. A bulk run SHALL be started only after a small probe succeeds, is reported, and the user explicitly approves.

#### Scenario: G0 stays within red lines
- **WHEN** a G0 task would train NOUE, edit the estimator backend, add an object factor, or launch the bulk recording
- **THEN** it is deferred to a later phase requiring explicit user approval
- **AND** only the small probe and standalone tooling are produced in G0

#### Scenario: Bulk recording is gated on probe + approval
- **WHEN** the dynamic_v3 probe has not succeeded or the user has not approved
- **THEN** no bulk recording is started

### Requirement: Phased gates with stop-and-report
The work SHALL proceed through gates G0 (data grounding) → G1 (raw-estimator validation) → G2 (NOUE training, incl. A2) → G3 (optional integration/utility), and SHALL stop and report status + data + provenance at each gate, leaving direction and go/no-go decisions to the user.

#### Scenario: Each gate stops for the user
- **WHEN** a gate's pass/hold criteria are evaluated
- **THEN** the result is reported with provenance
- **AND** the next phase starts only after the user decides
