## ADDED Requirements

### Requirement: Shared per-object track store
The system SHALL maintain a shared object memory keyed by track id, storing bbox or mask,
depth, 3D local position, velocity, track age, persistence state, per-state beliefs
(`p_static_anchor`, `p_transient`, `p_navigation_blocking`, `motion_uncertainty`), and
links to associated ORB keypoints and MapPoints.

#### Scenario: Track ingestion
- **WHEN** the detector/tracker publishes a per-detection record for a track id
- **THEN** the object memory SHALL create or update the corresponding track entry without
  requiring global timestamp synchronization across topics

#### Scenario: Persistence states
- **WHEN** a track entry is queried
- **THEN** its persistence state SHALL be exactly one of STATIC, CANDIDATE_ANCHOR,
  TRANSIENT_OBJECT, UNKNOWN

### Requirement: Rule-based persistence before learning
The system SHALL provide a rule-based persistence estimator (stationary duration, velocity
variance, depth stability, track age; class prior as weak feature only) as the default
belief source, and SHALL allow the learned estimator to replace it behind the same
interface.

#### Scenario: Rule fallback
- **WHEN** the learned persistence model is disabled or unavailable
- **THEN** the memory SHALL serve rule-based beliefs with identical message schema

### Requirement: Label timing and ownership voting contract
The system SHALL label keypoints between detector frames by track-state interpolation, and
SHALL assign MapPoint object ownership only after at least 3 labeled observations with
majority agreement; unresolved MapPoints SHALL be treated as UNKNOWN.

#### Scenario: Ownership before quorum
- **WHEN** a MapPoint has fewer than 3 labeled observations
- **THEN** its object ownership SHALL be UNKNOWN and its observation weight SHALL be the
  UNKNOWN weight (0.5)

#### Scenario: Interpolated labels
- **WHEN** a camera frame arrives with no detector output for up to the detector period
- **THEN** keypoint labels SHALL be derived from interpolated track bbox/mask state rather
  than dropped

### Requirement: Separated consumer interfaces
The system SHALL expose two consumer interfaces: a raw object layer (track kinematics and
rule dynamic probability, independent of backend state) and an anchor layer (persistence
states, candidate-anchor MapPoint support, promotion/demotion events, derived from backend
feedback).

#### Scenario: Planner-only ablation boundary
- **WHEN** the system runs in P2 (planner-only) configuration
- **THEN** the planner SHALL consume only the raw object layer, and anchor-layer topics
  SHALL NOT be subscribed by the planner process

#### Scenario: Coupled configuration
- **WHEN** the system runs in P3/P4 configuration
- **THEN** the planner SHALL consume anchor-layer support in its localization risk term

### Requirement: Learned persistence downgrade rule
The learned persistence module SHALL output `p_static_anchor`, `p_transient`,
`p_navigation_blocking`, and `motion_uncertainty` only; `p_loop_closure_safe` SHALL be
approximated by a high `p_static_anchor` threshold; if learned persistence does not improve
downstream endpoints over rule persistence, it SHALL be reported as analysis, not claimed
as a contribution.

#### Scenario: Downgrade verdict
- **WHEN** Gate 6 comparison shows learned ≤ rule on downstream endpoints
- **THEN** the evaluation report SHALL record C3 as downgraded and the paper claim SHALL
  exclude learned persistence as a main contribution

#### Scenario: Label hygiene
- **WHEN** a CARLA training label is generated for a track that leaves the field of view
  or becomes occluded
- **THEN** visibility loss SHALL NOT be used as evidence of motion; labels SHALL derive
  from ground-truth actor motion over the fixed horizon
