## ADDED Requirements

### Requirement: Evaluation is organized into four layers with fixed metrics

Evaluation SHALL be organized into four layers, each with datasets, metrics, and baselines fixed before results are read.

| Layer | Question | Datasets | Metrics |
|---|---|---|---|
| E1 obstacle reliability (real) | Is obstacle state reliable? | nuScenes, KITTI, CARLA | AURC, ECE, F1_invalid, overconfident-wrong, unsafe-velocity-accepted, TTC false-alarm/missed-risk proxy |
| E2 VINS health | Is localization unsafe (earlier than rules)? | CARLA replay, KAIST (+ KITTI/EuRoC if feasible) | false-safe rate, missed-alert rate, time-to-alert, AUROC, AURC, ECE, alert-limit-exceed detection |
| E3 closed-loop navigation | Does the supervisor reduce risk? | CARLA/Gazebo + frontier/Nav2 | collision, near-miss, false-safe, missed-risk, freezing, unnecessary-stop, mission-success, time-to-alert, recovery-success |
| E4 small real-system | Does it run and warn on real hardware? | user platform | qualitative warning/fallback demo + runtime/integration |

#### Scenario: Closed-loop compares four navigation policies

- **WHEN** E3 is run
- **THEN** it SHALL compare original navigation, rule-based-threshold supervisor, all-conservative policy, and the learned supervisor
- **AND** safety metrics SHALL be reported for all four under the same episodes

#### Scenario: E4 is a feasibility demonstration, not a statistical proof

- **WHEN** E4 is reported
- **THEN** it SHALL demonstrate VINS-health warning and FOG_COAST/STOP_REINIT feasibility plus runtime/integration
- **AND** it SHALL NOT be presented as large-scale statistical evidence

---

### Requirement: Kill criteria K0–K5 gate the claims

The change SHALL enforce the following kill criteria. When a criterion fires, the corresponding claim SHALL be downgraded or dropped, and the outcome SHALL be reported as a finding, not hidden.

- **K0** — fewer than `TBD-N` distinct localization divergence/alert events in available logs → VINS HealthNet downgraded to descriptive / rule-calibration (no learned claim).
- **K1** — Obstacle ReliabilityNet cannot beat simple baselines on real datasets → drop obstacle reliability as a main contribution (note: in-domain already passes; the live risk is cross-dataset without target calibration).
- **K2** — VINS HealthNet cannot predict unsafe/divergence earlier than rule-based (incl. `failureDetection() Bas>2.5`) on CARLA + ≥1 real dataset → drop the VINS-health learned claim.
- **K3** — the supervisor does not reduce collision / near-miss / false-safe in closed-loop versus original and rule-based → ship the rule-based integrity decision layer only; no learned-navigation-benefit claim.
- **K4** — FOG_COAST cannot keep drift within budget on KAIST-like or the small real test → drop the fallback-benefit claim; keep monitor-only warning.
- **K5** — all modules work only in CARLA and fail on real datasets → downgrade venue and narrow claim scope to what real data supports.

#### Scenario: A fired kill criterion becomes a reported finding

- **WHEN** K3 fires (no closed-loop safety reduction from the learned supervisor)
- **THEN** the paper SHALL report the rule-based integrity decision layer as the contribution
- **AND** the null learned-supervisor result SHALL be stated explicitly, not omitted

#### Scenario: K0 is checked before HealthNet training is scheduled

- **WHEN** Phase 2 begins
- **THEN** the K0 event-count probe SHALL run first
- **AND** training SHALL proceed only if the event count meets `TBD-N`

---

### Requirement: Simulation-only results are never presented as real-world claims

Any result obtained only in CARLA/Gazebo SHALL be labelled simulation-only until corroborated by a real dataset (KITTI/nuScenes/KAIST/EuRoC) or the user platform. The paper SHALL use conservative wording ("will evaluate", "is intended to", "shall not claim unless", "blocked until evidence") and SHALL NOT phrase a simulation finding as a demonstrated real-world capability.

#### Scenario: A CARLA-only supervisor result is scoped

- **WHEN** the supervisor reduces collisions only in CARLA and no real corroboration exists
- **THEN** the result SHALL be labelled CARLA-only
- **AND** the venue and claim scope SHALL be set by what real data supports (K5)

---

### Requirement: Determinism and isolation discipline apply to every reported number

VINS-dependent numbers SHALL be measured under isolation (no concurrent CARLA/CPU contention), consistent with the repository's established determinism discipline. Closed-loop and replay results SHALL report reps and variance; a single-run number SHALL NOT be a conclusion, and high-variance runs SHALL be repeated.

#### Scenario: Isolation is required for VINS numbers

- **WHEN** a VINS-health or closed-loop VINS-in-loop number is recorded
- **THEN** it SHALL be measured with the machine isolated from competing CARLA/VINS load
- **AND** the provenance (reps, variance, isolation state) SHALL be recorded with the result
