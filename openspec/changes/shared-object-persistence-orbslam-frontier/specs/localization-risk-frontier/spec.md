## ADDED Requirements

### Requirement: Four-term frontier utility with per-cycle normalization
Frontier goal scoring SHALL use exactly four terms in v1 — information gain, path cost,
dynamic occupancy risk, localization degradation risk — each min-max normalized across the
candidate frontier set per replan cycle, with fixed default weights subject to a
sensitivity sweep in evaluation; integrity/availability SHALL NOT be utility terms;
object disambiguation gain is out of scope for v1.

#### Scenario: Term set is closed
- **WHEN** frontier utility is computed in v1
- **THEN** no utility terms other than the four specified SHALL contribute to goal scoring

### Requirement: Localization risk on known traversal segments only
Localization degradation risk SHALL integrate expected visible static / candidate-anchor
support along predicted poses of the traversal path, evaluated ONLY over cells with known
occupancy status; the unknown frontier interior SHALL contribute information gain only and
SHALL NOT be penalized for lacking map points.

#### Scenario: Exploration deadlock avoidance
- **WHEN** a frontier borders a large unmapped region with zero map points beyond it
- **THEN** its localization risk SHALL be computed from the known approach segment only,
  and the unmapped interior SHALL NOT increase its risk

#### Scenario: Liveness under uniform high risk
- **WHEN** all candidate frontiers exceed the localization risk threshold
- **THEN** the planner SHALL select the minimum-risk frontier rather than selecting no goal

### Requirement: Explicit anchor-layer consumption in coupled mode
In coupled configurations (P3/P4) the localization risk term SHALL consume backend-derived
candidate-anchor / static support; in planner-only configuration (P2) it SHALL consume only
raw-object-layer occlusion and vanilla map-point density; implementation SHALL occur in
frontier goal scoring, with the Nav2 planning and control stack retained stock.

#### Scenario: Coupled risk uses anchors
- **WHEN** the system runs in P3 and a candidate path passes a region rich in
  CANDIDATE_ANCHOR support
- **THEN** that path's localization risk SHALL be lower than an otherwise identical path
  lacking anchor support

#### Scenario: No costmap-only shortcut
- **WHEN** localization or anchor information influences navigation
- **THEN** it SHALL do so through the frontier utility terms, not solely through Nav2
  keepout/speed filters or a risk bus
