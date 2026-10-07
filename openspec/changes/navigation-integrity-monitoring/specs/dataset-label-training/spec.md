## ADDED Requirements

### Requirement: Each dataset has a fixed role and label capability

Each dataset SHALL be used only for roles whose labels it can actually produce. The change SHALL NOT use a dataset for a claim it cannot label. Every real-world dataset used is physically available at `/mnt/sata4t/datasets/`.

| Dataset | Role | Labels it can produce |
|---|---|---|
| CARLA (411G) | closed-loop episodes; controlled VINS degradation; VINS-noise replay; FOG fallback sim | GT pose, GT obstacle pos/vel, collision/near-miss/mode-oracle |
| nuScenes (376G) | real obstacle-state reliability pretraining/eval | position_valid, velocity_valid, full_state_valid (real obstacle GT) |
| KITTI Tracking (12G) | real obstacle reliability; optional VO/VINS health | obstacle validity (LiDAR GT); pose from oxts |
| KAIST Urban (564G) | VINS HealthNet real train/eval; FOG_COAST feasibility | pose error vs RTK; FOG/wheel/IMU degradation; drift-vs-time |
| EuRoC (99G) | VIO health baseline (non-dynamic real failure) | pose error vs Vicon/Leica |
| Oxford RobotCar (optional) | long-term appearance/weather VINS-health generalization | pose vs reference (if setup feasible) |
| User real platform | deployment validation; small-scale fallback demo | qualitative + small-scale quantitative |

#### Scenario: nuScenes is not used as a stereo VINS benchmark

- **WHEN** nuScenes is used
- **THEN** it SHALL serve obstacle-state reliability (real obstacle pos/vel), not a stereo-VINS ATE benchmark
- **AND** any localization use of nuScenes SHALL be justified as feasible and labelled accordingly

#### Scenario: A claim without producible labels is forbidden

- **WHEN** a metric requires a label a dataset cannot produce (e.g., collision on a dataset with no closed-loop)
- **THEN** that metric SHALL NOT be reported on that dataset
- **AND** the claim SHALL be moved to a dataset that can produce the label

---

### Requirement: The training curriculum trains modules before integration

Training SHALL proceed Stage 1 → Stage 4 and SHALL NOT begin with an end-to-end model. Stage 1: Obstacle ReliabilityNet on nuScenes + KITTI (+ CARLA supplementary). Stage 2: VINS HealthNet on CARLA replay + KAIST (+ KITTI-raw/EuRoC if feasible), gated by the K0 event-count probe. Stage 3: Navigation Risk Supervisor on closed-loop episodes with frozen A/B outputs and a mandatory rule-based baseline. Stage 4: integrated temporal fusion (multi-task heads) only after Stages 1–3 succeed.

#### Scenario: End-to-end model is not the first model

- **WHEN** integration is considered
- **THEN** Stage 4 SHALL run only after Stages 1–3 produce calibrated, frozen module outputs
- **AND** a single end-to-end Transformer SHALL NOT be trained as the first or only model

#### Scenario: Frozen calibrated outputs feed the supervisor

- **WHEN** Stage 3 trains the supervisor
- **THEN** HealthNet and ReliabilityNet SHALL be frozen and calibrated
- **AND** the supervisor SHALL consume their outputs, not their raw internal features

---

### Requirement: The pose curriculum P1→P2→P3 is mandatory

Navigation-facing training SHALL use the pose curriculum: P1 GT/oracle pose (teacher policy for clean navigation risk); P2 VINS-noise replay (inject realistic drift, scale drift, yaw drift, delay, reset, and jump patterns from VINS replay logs); P3 live VINS-in-loop (validation only, not the first/primary training source). Navigation SHALL NOT be trained on GT pose only, and SHALL NOT be trained on live VINS only.

#### Scenario: VINS-noise replay precedes live VINS

- **WHEN** the supervisor is trained for degraded localization
- **THEN** P2 VINS-noise-replay episodes SHALL be used for scalable training
- **AND** P3 live VINS-in-loop SHALL be used for validation, not as the primary training source

#### Scenario: GT-only training is rejected

- **WHEN** a navigation training run uses only GT pose
- **THEN** it SHALL be treated as the P1 teacher stage only
- **AND** a P2 VINS-noise stage SHALL be required before any deployment-facing claim

---

### Requirement: No fabricated or placeholder data enters training or results

Every training example and reported number SHALL come from a real run on real or simulated data with recorded provenance. Placeholder CSVs, synthetic stand-ins for real runs, and raw-speed-as-classifier substitutions SHALL NOT be used.

#### Scenario: Missing data blocks the claim instead of being faked

- **WHEN** a required input (e.g., VINS replay features for a recording) is unavailable
- **THEN** the dependent result SHALL be marked blocked-until-evidence
- **AND** no placeholder value SHALL be substituted to complete a table
