## ADDED Requirements

### Requirement: Planner interface receives per-object validity class, not raw scores
The planner-facing interface SHALL abstract the component-wise validity scores into four object classes that correspond directly to conservative-planning responses:

| class | condition | planner response |
|---|---|---|
| `FULL_STATE_VALID` | all components > τ_hi | use position + velocity for TTC / occupancy |
| `POSITION_ONLY` | pos_valid > τ_hi, vel_valid < τ_lo | use position for occupancy only; skip TTC |
| `VELOCITY_UNCERTAIN` | pos_valid > τ_hi, vel_valid ∈ [τ_lo, τ_hi] | use position; apply conservative velocity prior |
| `INVALID` | pos_valid < τ_lo | treat as unknown occupied region; maximum conservatism |

The interface is **output-only** — no feedback from planner to the validity estimator or VINS.

#### Scenario: Valid vehicle for TTC
- **WHEN** a tracked vehicle has all components above τ_hi
- **THEN** it is classified FULL_STATE_VALID
- **AND** its position and velocity are passed to the planner for TTC and occupancy prediction
- **AND** no conservative prior is applied

#### Scenario: Vehicle beyond stereo depth range
- **WHEN** a vehicle is detected at > 50 m with depth estimate marked unreliable
- **THEN** it is classified INVALID (position_valid < τ_lo)
- **AND** the planner treats the region as unknown occupied
- **AND** TTC is not computed for this object

#### Scenario: Fresh detection, no velocity history
- **WHEN** a new pedestrian appears for the first time in frame N
- **THEN** it is classified POSITION_ONLY (track age < 3 → vel_valid < τ_lo, pos_valid may be high)
- **AND** the planner uses its position for a static occupancy buffer
- **AND** TTC is not computed until velocity history is established

---

### Requirement: Planner interface is evaluated on object-validity quality, not VINS ATE
The planner interface contribution is evaluated separately from the VINS routing contribution. Evaluation metrics for the planner interface are:

- **Precision** of FULL_STATE_VALID classification (what fraction of "valid" objects were actually valid by GT)
- **Recall** of INVALID classification (what fraction of invalid objects were correctly flagged)
- **False-positive rate** for POSITION_ONLY (valid-velocity objects incorrectly downgraded)
- **TTC error** for FULL_STATE_VALID objects (cm/s error in predicted vs GT TTC)

These metrics are computed on KITTI Tracking (LiDAR GT) and CARLA (GT per-instance velocity/pose).

#### Scenario: Precision evaluation on KITTI
- **WHEN** the classifier returns FULL_STATE_VALID for 150 objects across the KITTI tracking eval set
- **THEN** the precision is computed as: number of those 150 where GT speed > 1.0 m/s AND GT position error < 2 m / 150
- **AND** this metric is reported separately from any VINS ATE result

---

### Requirement: Planner interface does not feed back into VINS
The validity scores and object classes produced for the planner interface are computed after the VINS solve, using the VINS-estimated ego pose as context. They do not feed back into the VINS factor graph.

There is no loop: validity → planner → VINS update. The architecture is strictly:
```
VINS solve → ego pose → object state estimation → validity module → planner interface
```

#### Scenario: No feedback loop
- **WHEN** the planner receives an INVALID object
- **THEN** it uses this for planning only
- **AND** no signal propagates back to the VINS estimator
- **AND** the next VINS keyframe is computed identically with or without the planner having received the object

---

### Requirement: nuScenes is used for planner-interface evaluation only, not stereo-VINS benchmark
nuScenes data SHALL be used to evaluate the planner-facing validity interface (object classification quality, TTC error) using nuScenes' own GT annotations and ego poses. nuScenes SHALL NOT be used as a stereo-VINS localization benchmark — the nuScenes camera rig (ring cameras, fisheye) is not compatible with this system's stereo-VINS configuration.

#### Scenario: nuScenes used correctly
- **WHEN** object validity results are reported for nuScenes
- **THEN** they reference object classification metrics (precision, recall, TTC error) against nuScenes GT boxes
- **AND** no ATE or RPE localization metrics are reported for nuScenes
- **AND** no "nuScenes VINS baseline" is established

#### Scenario: nuScenes misuse is rejected
- **WHEN** a proposed experiment attempts to run the stereo-VINS estimator on nuScenes data
- **THEN** it SHALL be rejected as out-of-scope for this change
- **AND** a note SHALL be added to the non-goals section
