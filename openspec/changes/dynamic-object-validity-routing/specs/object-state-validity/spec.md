## ADDED Requirements

### Requirement: Component-wise validity decomposition
The object-state validity module SHALL decompose object validity into three independent components — position, velocity, and full-state — and SHALL output a scalar score in [0,1] for each component per object per frame.

The three components are defined as:
- `P_position_valid`: the estimated object position (in body or world frame) is trustworthy for navigation use
- `P_velocity_valid`: the estimated object velocity vector is trustworthy for motion prediction
- `P_full_state_valid`: the joint (position, velocity, orientation, track continuity) is trustworthy

Each component may fail independently. Position validity depends on stereo depth range, occlusion, and detection confidence. Velocity validity depends on tracker age, optical-flow consistency, and ego-motion compensation quality. Full-state validity is the minimum of all component validities, not their product.

#### Scenario: Components fail independently
- **WHEN** an object is at the edge of stereo depth range (beyond 50 m)
- **THEN** `P_position_valid` SHALL be low
- **AND** `P_velocity_valid` MAY remain high if the track has long history and consistent optical flow
- **AND** `P_full_state_valid` SHALL be low (bounded by lowest component)

#### Scenario: Fresh detection has no velocity history
- **WHEN** a detection has track age < 3 frames
- **THEN** `P_velocity_valid` SHALL be low regardless of raw speed estimate
- **AND** `P_position_valid` MAY be non-zero if depth estimate is reliable
- **AND** the module SHALL NOT use raw_speed as a proxy for velocity validity without age gating

#### Scenario: Fully valid object
- **WHEN** a tracked vehicle has age ≥ 5 frames, depth within stereo range, consistent track, ego-compensation applied
- **THEN** all three components SHALL return scores above a threshold defined in the evaluation protocol
- **AND** the routing policy SHALL return ACCEPT or no-change

---

### Requirement: Routing policy is derived from component scores, not raw detection
The routing policy output (`routing_policy ∈ {REJECT, DOWNWEIGHT, ACCEPT}`) SHALL be a deterministic function of the component scores and configured thresholds. It SHALL NOT be based on raw detection confidence, class, or speed alone.

#### Scenario: REJECT policy from low position validity
- **WHEN** `P_position_valid < τ_reject` (configurable, default 0.3)
- **THEN** routing_policy SHALL be REJECT
- **AND** the VINS consumer SHALL mask the object's bbox in the LEFT image for feature suppression

#### Scenario: DOWNWEIGHT from moderate validity
- **WHEN** `P_position_valid ∈ [τ_reject, τ_accept]`
- **THEN** routing_policy SHALL be DOWNWEIGHT
- **AND** the VINS consumer SHALL apply reduced feature weight (soft routing) if soft weighting is enabled
- **AND** if only hard routing is enabled, DOWNWEIGHT SHALL map to REJECT

#### Scenario: ACCEPT from high validity
- **WHEN** all components exceed τ_accept (configurable, default 0.7)
- **THEN** routing_policy SHALL be ACCEPT
- **AND** no masking or weighting change occurs

---

### Requirement: Raw speed is a baseline signal, not a validity estimate
`raw_speed_ms` (object velocity magnitude from raw stereo-depth + optical-flow, no smoothing, no history) is a measurement, not a validity estimate. It SHALL NOT be used as the TCSV-M classifier output. It SHALL be used only as a baseline comparison and a training-set analysis signal.

#### Scenario: raw_speed used as TCSV-M is rejected
- **WHEN** any evaluation step proposes using raw_speed threshold as the formal validity estimator
- **THEN** the evaluation SHALL be classified as a baseline comparison, not a TCSV-M result
- **AND** a proper TCSV-M result must come from the trained classifier with defined features and training procedure

---

### Requirement: GT is used only for oracle evaluation and offline training, never at runtime
Ground-truth dynamic object state (`gt_speed_ms`, `gt_pos`, per-instance velocity from CARLA) SHALL only be used for:
1. Building `oracle` mask variants (eval upper bound)
2. Generating training labels for the offline TCSV-M training pipeline
3. Post-hoc diagnostic analysis

GT SHALL NOT be available at inference time. Any runtime estimate must come from the detection-tracking-estimation pipeline.

#### Scenario: Oracle variant uses GT
- **WHEN** the oracle mask variant is evaluated
- **THEN** it uses GT-confirmed moving objects and represents the theoretical upper bound
- **AND** it is labelled as oracle (GT; eval only) in all tables and figures
- **AND** it is not claimed as a deployable result

#### Scenario: TCSV-M runtime uses no GT
- **WHEN** TCSV-M is deployed for VINS routing
- **THEN** all its inputs are observable at runtime: detection bbox, track age, raw speed, track history, depth estimate, ego velocity
- **AND** no GT field is used

---

### Requirement: Validity output is per-object, per-frame, not per-scene
The module SHALL output a validity record for every detected object in every frame, not a single scene-level flag. Routing decisions are made at the per-object level, not per-frame.

#### Scenario: One valid and one invalid object in the same frame
- **WHEN** frame N contains a valid slow-moving vehicle (long track, near range) and an invalid fast-moving pedestrian (short track, outside stereo range)
- **THEN** only the invalid object's bbox is routed to REJECT
- **AND** the valid object's features are retained unchanged
- **AND** the frame-level masking is not applied uniformly
