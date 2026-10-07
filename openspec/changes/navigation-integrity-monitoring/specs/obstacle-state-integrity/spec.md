## ADDED Requirements

### Requirement: The obstacle source is modular and the contribution is the reliability layer

The obstacle-state integrity channel SHALL accept obstacle observations from any of a set of interchangeable sources — YOLO+ByteTrack+stereo depth, CARLA GT, KITTI/nuScenes GT, or LiDAR/depth/costmap — through a common per-object observation schema. No claim SHALL depend on a specific detector, and no detector SHALL be presented as a contribution. The contribution is the reliability/integrity estimate over obstacle state and its use by navigation.

#### Scenario: Swapping the obstacle source does not change the claim

- **WHEN** the obstacle source is switched from YOLO+stereo to LiDAR/depth for the same scene
- **THEN** the ReliabilityNet SHALL consume the same per-object observation schema and emit the same output fields
- **AND** the paper's contribution and evaluation SHALL remain the reliability layer, not the detector

#### Scenario: Detector quality is a controlled input, not a result

- **WHEN** results are reported across obstacle sources
- **THEN** the detector/source SHALL be named as an experimental condition
- **AND** no result SHALL be phrased as "our detector improves detection"

---

### Requirement: Obstacle reliability decomposes into position, velocity, and full-state components

The channel SHALL emit `P_position_valid`, `P_velocity_valid`, `P_full_state_valid`, `sigma_position`, `sigma_velocity`, and obstacle protection levels `OPL_position`, `OPL_velocity` per object per frame. The three validity components fail independently: position validity depends on depth range / occlusion / confidence; velocity validity depends on track age / bearing observability / ego-compensation; full-state validity is the minimum of the components, not their product.

#### Scenario: Far object has valid velocity refused

- **WHEN** an object is beyond reliable depth range (velocity error grows with distance)
- **THEN** `P_velocity_valid` SHALL be low and `OPL_velocity` SHALL be large
- **AND** `P_position_valid` MAY remain higher if depth is still usable
- **AND** `P_full_state_valid` SHALL be bounded by the lowest component

#### Scenario: Fresh track has no velocity

- **WHEN** an object's track age is below the minimum window
- **THEN** `P_velocity_valid` SHALL be low regardless of raw speed
- **AND** raw speed SHALL NOT be used as a validity estimate (baseline only)

---

### Requirement: Validity thresholds are fixed before evaluation

The validity labels SHALL use fixed, documented thresholds — `position_valid = 1[position_error ≤ 3 m]`, `velocity_valid = 1[velocity_error ≤ 3 m/s]` (optionally AND `dir_err ≤ 45°`), `full_state_valid = position_valid AND velocity_valid` — with an ego-independent error criterion so ego motion cancels. Thresholds SHALL be frozen before results are read and SHALL NOT be re-tuned per dataset afterward; threshold ablations SHALL be reported as sensitivity, not as the headline number.

#### Scenario: Ego-independent velocity error

- **WHEN** velocity validity is labelled
- **THEN** the error SHALL be `||raw_vel − gt_vel||` in a frame where ego motion cancels
- **AND** the 3 m/s threshold SHALL be applied identically across CARLA, KITTI, and nuScenes

#### Scenario: No post-hoc threshold tuning

- **WHEN** a dataset yields weaker results at the fixed threshold
- **THEN** the threshold SHALL remain fixed and the weaker result SHALL be reported honestly
- **AND** any alternative threshold SHALL appear only in a labelled sensitivity ablation

---

### Requirement: Obstacle reliability must beat interpretable baselines and calibrate its protection level

The channel SHALL be compared against distance-gate, bbox-area-gate, detection-confidence-gate, raw-speed-gate, constant-velocity-smoothing-gate, and an all-conservative policy. It SHALL report AURC, AUROC, F1_invalid, ECE, overconfident-wrong-velocity, unsafe-velocity-accepted, risk-at-fixed-coverage, and valid-retention-at-fixed-risk. `OPL` SHALL be calibrated so its exceedance rate meets the target integrity risk. The learned model SHALL use fixed-window temporal pooling; deep sequence models SHALL NOT be adopted unless they beat pooling with a confident interval.

#### Scenario: Protection level is calibrated to integrity risk

- **WHEN** `OPL_position` is emitted at target integrity risk IR
- **THEN** held-out exceedance `P(true error > OPL_position)` SHALL be ≤ IR within calibration tolerance
- **AND** miscalibration SHALL be corrected by recalibrating OPL, not by moving the 3 m label

#### Scenario: Cross-dataset generalization is reported honestly (K1)

- **WHEN** a model trained on one dataset is evaluated on another real dataset without target-domain calibration
- **THEN** the direct-transfer number SHALL be reported even if weak (prior CARLA→KITTI transfer was +0.034 AUROC)
- **AND** IF direct transfer fails, the requirement for target-domain calibration SHALL be stated, not hidden
