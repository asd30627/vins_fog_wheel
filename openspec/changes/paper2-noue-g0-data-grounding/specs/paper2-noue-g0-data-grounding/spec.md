## ADDED Requirements

### Requirement: G0 stays low-risk — no estimator backend change, no training, no object factor
The G0 data-grounding work SHALL NOT modify the VINS-Fusion estimator backend, SHALL NOT add any object factor to the factor graph, SHALL NOT train the NOUE model, and SHALL NOT refactor the main project. All G0 outputs SHALL be standalone scripts and reports plus a GT-field-only change to the CARLA recorder.

#### Scenario: A change touches the estimator backend
- **WHEN** a proposed G0 task would edit the VINS-Fusion estimator backend, add an object factor, or train a model
- **THEN** it is rejected as out of scope for this change and deferred to a later change requiring explicit user approval

#### Scenario: G0 deliverables are standalone
- **WHEN** G0 produces tooling
- **THEN** it is delivered as standalone scripts (`scripts/paper2_*.py`, `*_probe.sh`) and repo-root reports
- **AND** the only edit to existing code is adding GT fields to the CARLA recorder per-instance record

### Requirement: CARLA recorder change is limited to GT fields
The CARLA recorder change SHALL be limited to adding ground-truth fields to the per-instance record (minimally `type_id`), and SHALL NOT alter the main recording flow, sensor set, or timing. Because `fwvio_ws` is not a git repository, the change SHALL be recorded via a backup copy plus a unified diff.

#### Scenario: Recorder change adds only GT fields
- **WHEN** `collect_carla_v2.py` is modified
- **THEN** the only change is adding GT field(s) such as `type_id` to the per-instance dict
- **AND** a backup and a unified diff are produced as provenance

### Requirement: Bulk CARLA recording is gated behind a successful probe and user approval
A full-scale CARLA recording campaign (on the order of ~30 runs) SHALL NOT be started automatically. It SHALL be started ONLY after a small dynamic_v3 probe has succeeded, its output has been verified and reported, and the user has explicitly approved the bulk run.

#### Scenario: Probe must precede bulk
- **WHEN** the dynamic_v3 probe has not yet succeeded or has not been approved by the user
- **THEN** no bulk recording is performed
- **AND** only the single small probe (≤80 frames, npc 15, with aux) is attempted

#### Scenario: CARLA server is not available
- **WHEN** the CARLA server is not running at probe time
- **THEN** the probe is not run and the server is NOT auto-started
- **AND** the blocked status, server state, and required user action are reported

### Requirement: Raw object probe results are honest or blocked, never fabricated
The minimal raw object pipeline SHALL report a real distance-binned error table only when object-position GT is available. When the GT-bearing probe data is not yet available, the pipeline SHALL report a BLOCKED status that states exactly what is missing, and SHALL NOT fabricate any error numbers.

#### Scenario: GT not available
- **WHEN** dynamic_v3 probe data with object-position GT does not exist
- **THEN** the raw object probe emits a BLOCKED report naming the missing inputs
- **AND** the standalone script remains runnable against a supplied data path

### Requirement: VINS-quality conditioning uses existing features only in G0
The NOUE conditioning feature schema (v0) SHALL be built from features already emitted by the existing `reliability_features_vins.csv`, and G0 SHALL NOT add new estimator logging (marginalization-prior residual, IMU-preintegration residual, parallax statistics, pose-covariance proxy are deferred).

#### Scenario: A v0 feature requires new logging
- **WHEN** a candidate conditioning feature is not present in the existing reliability CSV
- **THEN** it is excluded from the v0 schema and marked as deferred to a later, separately approved change
