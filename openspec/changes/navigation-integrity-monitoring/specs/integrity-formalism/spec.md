## ADDED Requirements

### Requirement: Integrity vocabulary is instantiated for VIO and obstacle state

The monitor SHALL define, for each integrity channel, an alert limit (AL), a runtime protection level (PL), and a target integrity risk (IR), reusing the GNSS/RAIM integrity model. AL is the maximum true error tolerable for safe navigation. PL is a runtime-computed bound such that `P(true_error > PL) ≤ IR`. The monitor SHALL NOT assert any numeric AL, PL bound, or IR value that has not been grounded by data; ungrounded numbers SHALL be marked `TBD-XX`.

Two channels are defined: the localization integrity channel (LPL, localization AL) and the obstacle-state integrity channel (OPL, obstacle AL). The two channels SHALL be computed independently and SHALL NOT feature-concatenate one channel's inputs into the other.

#### Scenario: Protection level bounds true error at target risk

- **WHEN** the obstacle channel emits `OPL_position = p` for an object with obstacle AL = 3 m
- **THEN** the calibration procedure SHALL demonstrate `P(true position error > p) ≤ IR` on held-out data
- **AND** if the empirical exceedance rate is above IR, the PL SHALL be recalibrated (isotonic/conformal), not the label threshold

#### Scenario: Ungrounded bound is marked TBD

- **WHEN** a localization alert limit is required but not yet grounded by planner safety margin or data
- **THEN** the spec and code SHALL reference it as `TBD-AL-LOC`
- **AND** no evaluation SHALL report a pass/fail against a numeric localization AL until `TBD-AL-LOC` is resolved with recorded provenance

---

### Requirement: Hazardously misleading information (false-safe) is the primary failure to minimize

The monitor SHALL treat HMI — the event `PL < AL` while `true_error ≥ AL` — as the primary failure mode. Every channel evaluation SHALL report the HMI (false-safe) rate as a first-class metric, separately from availability (false-alert) cost. The monitor SHALL be tuned to minimize HMI at a stated availability, not to maximize accuracy.

#### Scenario: HMI is counted when the monitor under-bounds a real error

- **WHEN** an object's true velocity error is 6 m/s (obstacle velocity AL = 3 m/s) but `OPL_velocity` implies the estimate is within limit
- **THEN** the frame SHALL be counted as an HMI (false-safe) event for the obstacle velocity channel
- **AND** the object SHALL be included in the `unsafe_velocity_accepted` count

#### Scenario: False alert is counted separately as availability cost

- **WHEN** the monitor raises `PL ≥ AL` but the true error is within AL
- **THEN** the frame SHALL be counted as a false alert (availability cost), NOT as HMI
- **AND** false-alert rate and HMI rate SHALL be reported as distinct numbers, never summed into a single accuracy figure

---

### Requirement: Each channel produces a Stanford integrity diagram

Each integrity channel SHALL be evaluated with a Stanford integrity diagram plotting PL (vertical) against true error (horizontal), partitioned into nominal, system-available, misleading-information (MI), and hazardously-misleading-information (HMI) regions. The diagram SHALL be produced on both simulation and at least one real dataset per channel.

#### Scenario: Diagram partitions events into integrity regions

- **WHEN** the localization channel is evaluated on a dataset with GT pose
- **THEN** each sample SHALL be placed on the LPL-vs-true-error plane
- **AND** counts SHALL be reported for nominal, available, MI (PL ≥ error ≥ AL but PL under a stricter bound), and HMI (error ≥ AL > PL) regions
- **AND** any point in the HMI region SHALL be listed in a failure gallery with its runtime features

---

### Requirement: Time-to-alert is measured, not assumed

For predictive outputs (`unsafe_in_1s`, `unsafe_in_3s`, `diverging_soon`), the monitor SHALL measure time-to-alert (TTA) as the lead time between the monitor raising an alert and the true error crossing AL. TTA SHALL be reported as a distribution (median, p10, p90), and compared against rule-based baselines' TTA. A negative or zero TTA (alert raised at or after the true crossing) SHALL be reported as a missed-lead event.

#### Scenario: Lead time is credited only before the true crossing

- **WHEN** the monitor raises `unsafe_in_1s = 1` at time t and the true error crosses AL at time t+0.7 s
- **THEN** TTA SHALL be recorded as +0.7 s
- **AND** IF the crossing had occurred at t−0.2 s (before the alert), TTA SHALL be recorded as a missed-lead event, not a positive lead

---

### Requirement: The integrity chain links formalism to closed-loop outcome

The monitor SHALL preserve a traceable chain from PL/AL to navigation action to closed-loop outcome: a mode switch SHALL be attributable to a channel crossing `PL ≥ AL`, and closed-loop safety metrics (collision, near_miss, false_safe) SHALL be reportable conditioned on which channel triggered. The work SHALL NOT present the closed-loop result as an independent contribution disconnected from the PL/AL formalism.

#### Scenario: A mode switch is attributable to a protection-level crossing

- **WHEN** the supervisor switches NORMAL → FOG_COAST during a closed-loop episode
- **THEN** the trigger record SHALL identify the localization channel `LPL ≥ AL_loc` crossing that caused it
- **AND** the episode's collision/near-miss/false-safe outcome SHALL be attributable to that channel in the per-channel analysis
