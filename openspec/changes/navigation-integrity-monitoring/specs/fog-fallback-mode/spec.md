## ADDED Requirements

### Requirement: FOG fallback is a decision problem, not an engineering trick

The contribution of the fallback modes SHALL be learning when to switch, which mode to select, how early to warn, and how much false-safe / missed-risk is reduced — NOT the FOG/IMU propagation itself. The spec SHALL NOT present FOG_COAST as a hand-coded if-else branch; every fallback decision SHALL be driven by the calibrated localization channel and the drift budget.

#### Scenario: Fallback is triggered by integrity, not by a fixed timer

- **WHEN** the supervisor enters FOG_COAST
- **THEN** the entry SHALL be attributable to `LPL ≥ AL_loc` with `last_safe_time` available and drift within budget
- **AND** the entry SHALL NOT be a fixed-time or hard-coded rule disconnected from the integrity estimate

---

### Requirement: FOG_COAST admissibility conditions are explicit and budgeted

FOG_COAST SHALL be admissible only when all hold: localization unsafe or diverging soon; `last_safe_time` exists; FOG/IMU propagation drift from `last_safe_time` to now ≤ drift budget; navigation risk low enough to continue slowly; expected fallback duration ≤ `T_max`. The drift budget, `T_max`, and integrity risk SHALL be marked `TBD` until grounded by measured real-FOG drift; the spec SHALL NOT assert numeric budgets before grounding.

#### Scenario: Over-budget propagation forbids FOG_COAST

- **WHEN** projected FOG/IMU drift from `last_safe_time` to now exceeds the drift budget
- **THEN** FOG_COAST SHALL NOT be selected
- **AND** the supervisor SHALL select STOP_REINIT or UNAVAILABLE according to obstacle/navigation risk

#### Scenario: Budgets remain TBD until measured

- **WHEN** the drift budget or `T_max` is required but the real-FOG drift-vs-time curve is not yet measured
- **THEN** they SHALL be referenced as `TBD-drift-budget` / `TBD-Tmax`
- **AND** no FOG_COAST benefit SHALL be claimed against an ungrounded budget

---

### Requirement: FOG_COAST feasibility is grounded on real navigation-grade FOG

FOG_COAST feasibility SHALL be established by measuring achievable coasting duration within a drift budget on real navigation-grade FOG data (KAIST Urban, ~0.05°/hr), during simulated VINS outages. The measurement SHALL produce a drift-vs-time curve that sets the budget and `T_max`. Grade physics from the sibling grade-conditioned work applies: grade effects need minutes to integrate, so short coasts are the feasible regime and SHALL be characterized as such.

#### Scenario: Drift-vs-time curve sets the budget

- **WHEN** a VINS outage of duration d is simulated over KAIST real-FOG segments
- **THEN** the FOG/IMU propagated pose error at d SHALL be measured against GT (RTK)
- **AND** the maximum d keeping error within the safety bound SHALL define `T_max` for that grade

#### Scenario: Fallback benefit is not claimed if drift escapes budget (K4)

- **WHEN** FOG_COAST cannot keep drift within budget on KAIST-like real data or the small real test
- **THEN** the fallback-benefit claim SHALL be dropped
- **AND** the monitor SHALL still report the localization-integrity warning capability independent of any fallback claim

---

### Requirement: STOP_REINIT and UNAVAILABLE are defined by recovery feasibility

STOP_REINIT SHALL be selected when localization is unsafe and FOG uncertainty exceeds the budget or obstacle/navigation risk is too high or VINS cannot recover while moving. UNAVAILABLE SHALL be selected when VINS cannot recover, FOG uncertainty is too high, and the planner cannot guarantee safety. Recovery-success rate SHALL be reported for STOP_REINIT episodes.

#### Scenario: Failed reinit escalates to UNAVAILABLE

- **WHEN** STOP_REINIT is entered and VINS reinitialization does not succeed within the recovery window
- **THEN** the supervisor SHALL escalate to UNAVAILABLE and fail safe
- **AND** the episode SHALL be counted in recovery-failure statistics
