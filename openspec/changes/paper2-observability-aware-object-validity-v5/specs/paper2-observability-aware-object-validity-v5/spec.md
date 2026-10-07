## ADDED Requirements

### Requirement: v5 is an observability-aware validity layer, not feature-conditioning / dynamic SLAM
The work SHALL be framed as an observability-aware **validity layer** that decides when a dynamic object's position/velocity can be trusted, and SHALL NOT be framed as VINS-quality feature conditioning (the retired v4 A2), dynamic SLAM, object-aided localization, an object factor, a detector/tracker improvement, trajectory prediction, generic uncertainty estimation, or a conformal-risk-tube method.

#### Scenario: Framing stays on observability/validity
- **WHEN** the contribution is stated
- **THEN** it is "decide when to output full-state / position-only / invalid-velocity / unobservable / conservative-warning for dynamic objects under GPS-denied geometry"
- **AND** VINS-quality concatenation, dynamic SLAM, and conformal risk tube are explicitly non-goals

#### Scenario: v4 negative result is preserved, not repackaged
- **WHEN** v5 references the v4 A2 result
- **THEN** it reports A2 as not-promising/weak (honest) and does NOT claim it succeeded
- **AND** v4 artifacts are not deleted

### Requirement: OVI is geometric and interpretable, not a black box
The Observability Validity Index SHALL be an interpretable function of runtime-observable geometric quantities (at least `yaw_lever = range·sin(yaw_sigma)`, `bearing_change_rate`, `depth_noise_proxy(disparity)`, `velocity_observability_proxy = bearing_change/range`), with each term ablatable, and SHALL NOT be a black-box MLP. A light calibration (e.g. isotonic/logistic) to validity labels is allowed on top of the interpretable index.

#### Scenario: OVI terms are inspectable and ablatable
- **WHEN** OVI is reported
- **THEN** its terms are written as formulas and each can be ablated
- **AND** OVI is compared against single-factor baselines (distance-only, depth-only, bearing-only) on invalid-velocity detection

### Requirement: Validity labels and thresholds are reported, not asserted as ground truth
Validity labels (position_valid, velocity_valid, full_state_valid, position_only, invalid_velocity, unobservable_candidate, high_risk_object) SHALL be derived by stated threshold rules, and the thresholds SHALL be written in the report as choices subject to ablation, not as absolute truth.

#### Scenario: Thresholds are explicit and ablatable
- **WHEN** validity labels are built
- **THEN** the rules (e.g. pos_err≤3m, speed_err≤3 and dir_err≤45°) appear in the report
- **AND** they are flagged as ablatable (e.g. 2/3/5 m), not absolute

### Requirement: Refusal-aware policy is evaluated against no-refusal and v4 baselines
The refusal-aware state policy SHALL emit levels {full_state, high_covariance, position_only, velocity_invalid, unobservable, conservative_warning} and SHALL be evaluated against (a) a no-policy baseline that always outputs velocity and (b) the v4 NOUE policy, reporting overconfident-wrong-velocity, invalid-velocity recall/precision, planner-usable ratio, and false-refusal rate.

#### Scenario: Policy must beat always-output-velocity without excessive refusal
- **WHEN** the refusal policy is evaluated
- **THEN** overconfident-wrong-velocity vs the no-policy baseline is reported
- **AND** the false-refusal rate (refusing actually-valid velocity) is reported so the trade-off is visible

### Requirement: Object-consistency ego diagnostic stays offline and is reported honestly
The optional object-consistency ego-degradation diagnostic SHALL be offline correlation analysis only (object fake-lateral-velocity consistency vs VINS scale/feature/outlier degradation), SHALL NOT feed back to VINS, add an object factor, or claim any localization improvement, and SHALL be marked weak/null if the correlation is not clear.

#### Scenario: Diagnostic does not touch localization
- **WHEN** the ego diagnostic runs
- **THEN** it only correlates object-motion consistency with VINS degradation indicators offline
- **AND** no VINS feedback / object factor / localization-improvement claim is made

#### Scenario: Weak diagnostic is reported as weak
- **WHEN** the correlation is not clear
- **THEN** the diagnostic is labelled weak/null and not packaged as a positive result

### Requirement: v5 stays standalone — no backend, no factor, no G3, no re-recording
v5 SHALL be delivered as standalone scripts and reports consuming existing artifacts (24-run dataset, object benchmark, VINS replay results), and SHALL NOT modify the VINS backend, add an object factor, build a G3 backend scaffold, or record new CARLA data unless a clear data gap is identified and approved.

#### Scenario: A v5 task would touch the backend or re-record
- **WHEN** a proposed v5 step would edit the estimator backend, add an object factor, build G3 scaffold, or launch CARLA recording
- **THEN** it is rejected/deferred and flagged for explicit user approval

### Requirement: No overclaiming of novelty
The paper SHALL avoid "first" claims unless clearly verified, and SHALL position via "to our knowledge", "we focus on", "unlike methods that…", and an explicit literature-positioning report stating what cannot be claimed.

#### Scenario: Positioning is hedged and evidenced
- **WHEN** novelty is stated
- **THEN** it uses hedged language and cites the positioning report
- **AND** any close prior work is acknowledged with an explicit difference statement
