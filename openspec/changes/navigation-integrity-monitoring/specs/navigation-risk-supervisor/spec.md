## ADDED Requirements

### Requirement: The supervisor acts on top of the planner and estimator, never inside them

The navigation risk supervisor SHALL act as a supervisory layer above the closed-loop base (default Nav2/frontier) and above the VINS backend, using only published interfaces (speed-scale, mode-trigger, veto/permission). It SHALL NOT modify the Nav2/frontier core planner and SHALL NOT modify the VINS estimator backend. With the supervisor disabled, closed-loop behaviour SHALL be identical to the unmodified stack.

#### Scenario: Supervisor influences motion without editing the planner

- **WHEN** the supervisor recommends `recommended_speed_scale = 0.4` and `risk_mode = CAUTION`
- **THEN** it SHALL apply the scale and mode through the planner's published command/parameter interface
- **AND** the Nav2/frontier planning algorithm and the VINS backend SHALL remain unmodified

#### Scenario: Disabled supervisor is a no-op

- **WHEN** the supervisor is disabled (flag-OFF)
- **THEN** the closed-loop stack SHALL produce the same trajectory as the baseline stack without the monitor
- **AND** this equivalence SHALL be verified before any comparative closed-loop result is reported

---

### Requirement: The supervisor consumes frozen calibrated channel outputs plus navigation context

The supervisor SHALL consume frozen, calibrated outputs of VINS HealthNet (incl. LPL) and Obstacle ReliabilityNet (incl. OPL), together with navigation context: min obstacle distance, min TTC, local costmap density, frontier distance, planner valid/invalid signal, cmd_vel, oscillation/stuck proxy, emergency-stop flag, and current mode. It SHALL emit `P_collision_or_near_miss`, `P_freezing`, `P_unnecessary_stop`, `risk_mode`, `recommended_speed_scale`, and `fallback_permission`. It SHALL NOT re-derive one integrity channel from the other.

#### Scenario: Two independent risk sources are combined, not coupled

- **WHEN** the supervisor forms its risk estimate
- **THEN** it SHALL take LPL and OPL as separate calibrated inputs
- **AND** it SHALL NOT feed obstacle features into the localization estimate or vice versa

---

### Requirement: Risk modes are defined by integrity conditions

The supervisor SHALL select `risk_mode ∈ {NORMAL, CAUTION, FOG_COAST, STOP_REINIT, UNAVAILABLE}` according to the integrity conditions below. A mode change SHALL be attributable to a specific channel crossing `PL ≥ AL` or a specific navigation-context trigger.

- NORMAL: localization safe, obstacle risk low, planner healthy.
- CAUTION: localization or obstacle risk elevated → reduce speed, enlarge margin, continue carefully.
- FOG_COAST: localization unsafe/diverging, `last_safe_time` exists, FOG/IMU propagation within drift budget, navigation risk low enough to continue slowly.
- STOP_REINIT: localization unsafe, FOG uncertainty over budget OR obstacle/navigation risk too high → stop and attempt VINS reinit.
- UNAVAILABLE: cannot guarantee localization or navigation safety → fail safe.

#### Scenario: Elevated obstacle risk triggers CAUTION

- **WHEN** OPL for a near obstacle implies its state may be unsafe to act on while localization remains safe
- **THEN** the supervisor SHALL select CAUTION and reduce speed
- **AND** the trigger record SHALL attribute the switch to the obstacle channel

#### Scenario: Localization loss with headroom triggers FOG_COAST

- **WHEN** `LPL ≥ AL_loc` and `last_safe_time` exists and FOG propagation is within budget and navigation risk is low
- **THEN** the supervisor SHALL select FOG_COAST rather than STOP_REINIT
- **AND** IF FOG propagation exceeds the budget or obstacle risk is high, it SHALL select STOP_REINIT instead

---

### Requirement: A rule-based supervisor is the baseline and the fallback deliverable

The change SHALL implement a rule-based supervisor built from the same calibrated channels as the mandatory baseline. A learned-supervisor benefit SHALL be claimed only if the learned supervisor beats the rule-based supervisor on held-out closed-loop episodes with genuine generalization (unseen towns/routes). If it does not, the rule-based integrity decision layer SHALL be the reported deliverable and the learned-supervisor claim SHALL be dropped (see K3).

#### Scenario: Learned supervisor must generalize to unseen scenarios

- **WHEN** the learned supervisor is evaluated on held-out towns/routes not used in training
- **THEN** its collision / near-miss / false-safe reduction SHALL be compared against the rule-based supervisor on the same held-out set
- **AND** IF it does not beat rule-based, the paper SHALL report the rule-based layer as the contribution and SHALL NOT claim a learned navigation policy

---

### Requirement: The main claim is measured by safety metrics, not speed

Closed-loop evaluation SHALL report collision count, near-miss count, false-safe rate, missed-risk, minimum TTC, freezing time, unnecessary-stop count, mission-success rate, recovery-success rate, and time-to-alert. The main claim SHALL be a reduction in false-safe / collision / near-miss / missed-risk versus both the original navigation and the rule-based supervisor. Faster completion SHALL NOT be presented as success.

#### Scenario: A configuration that is faster but less safe is not a win

- **WHEN** a supervisor variant completes missions faster but increases near-miss or false-safe
- **THEN** it SHALL NOT be reported as an improvement
- **AND** the safety metrics SHALL take precedence over mission time in every comparison
