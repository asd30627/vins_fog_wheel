## ADDED Requirements

### Requirement: Two-sided anchor recovery gate
The evaluation SHALL demonstrate both failure modes before backend claims are made:
Side A — in a dense-dynamic suite, ORB-SLAM3 baseline (B1) degrades on at least one
localization endpoint, establishing the need for culling; Side B — in a low-static-texture
parked-vehicle suite, all-dynamic masking (B3) degrades relative to B1, establishing the
need for anchor recovery; the rule-anchor configuration SHALL match or beat the best of
B1/B3/B4 on both suites.

#### Scenario: Gate verdict recorded
- **WHEN** Gate 3 comparisons complete
- **THEN** a written verdict SHALL record whether Side A, Side B, and the rule-anchor
  condition each passed, and a NO-GO SHALL be escalated to the user before further
  backend work

### Requirement: Mandatory B4 geometric baseline
A geometric / optical-flow dynamic mask baseline (B4) SHALL be implemented and included in
all headline comparisons; learned-persistence claims SHALL identify where they exceed B4,
using stop-and-go and/or return-visit material where reactive geometric checks fail.

#### Scenario: Predictive advantage evidence
- **WHEN** learned persistence is claimed to outperform reactive baselines
- **THEN** the evidence SHALL include at least one stop-and-go or return-visit evaluation
  where B4 admits soon-to-move objects that persistence correctly rejects

### Requirement: Ablation matrix and coupling gain
The evaluation SHALL include B1 (ORB-SLAM3), B2 (VINS-Fusion, offline background only),
B3 (all-dynamic masking), B4 (geometric mask), B5 (object costmap only), P1 (backend only,
rule persistence), P2 (planner only, raw object layer), P3 (backend+planner, rule),
P4 (P3+learned), P5 (P3+oracle), P6 (utility-term ablation), P7 (culling without anchor
recovery); coupling gains SHALL be computed per primary endpoint as
backend_gain = P1−B1, planner_gain = P2−B1, combined_gain = P3−B1,
coupling_residual = combined_gain − backend_gain − planner_gain.

#### Scenario: Coupling claim validity
- **WHEN** the coupling residual is reported
- **THEN** the report SHALL verify that P2 consumed only the raw object layer, and the
  coupling claim SHALL rest on the planner's consumption of backend anchor support in P3/P4

### Requirement: Metric families
Evaluation SHALL report localization metrics (ATE/RPE, tracking lost/reset counts, map
contamination ratio, object-region MapPoint survival, candidate anchor survival, and —
conditional on resolving the known loop-rejection root cause — relocalization/loop
precision), navigation metrics (success rate, collision/near-miss, min clearance,
time-to-goal, path length, replan count, blocked frontier count), and integrity metrics
(false_safe, availability, unavailable time, HMI-like event count) as evaluation-only
quantities.

#### Scenario: Conditional loop metrics
- **WHEN** the `BAD LOOP!!!` root cause remains unresolved
- **THEN** loop-precision metrics SHALL be marked conditional and excluded from headline
  claims

### Requirement: Determinism and budget discipline
Headline numbers SHALL follow the determinism protocol (CARLA synchronous mode, fixed
seeds, machine isolation); the full ablation matrix SHALL run on 2 scenario suites with at
least 5 seeds each, with a pruned row set (B1/B3/B4/P3/P4) on remaining suites; all
edge-rate budgets SHALL be labeled planning targets, with the development hardware
(desktop RTX 5090) disclosed and no edge-hardware measurement implied.

#### Scenario: Planning-target labeling
- **WHEN** module rate budgets appear in any report or paper draft
- **THEN** they SHALL be explicitly labeled as planning targets, not measured edge results
