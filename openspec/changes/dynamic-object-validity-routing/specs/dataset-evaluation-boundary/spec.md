## ADDED Requirements

### Requirement: Dataset roles are fixed and exclusive — each dataset answers a specific question
Each dataset in the evaluation pipeline has a fixed, exclusive role. The roles do not overlap. A dataset that answers question Q1 is not re-purposed to answer Q2 without an explicit change proposal.

| dataset | role | answers |
|---|---|---|
| CARLA `dynamic_v3r7` (urban) | controlled VINS routing ablation | does masking help VINS? which towns? which grade? |
| CARLA `dynamic_v3r7` (Town06/07) | boundary / negative control | does VISION_INERT persist in non-urban? |
| KITTI Tracking | real object validity | do validity scores work on real LiDAR-GT data? |
| nuScenes | planner-facing object validity | do scores translate to real multi-camera scenes? |
| KAIST real car | optional FOG feasibility | does the method work on a real FOG platform? |
| EuRoC | static VINS sanity | is the base estimator unchanged? |

#### Scenario: CARLA used for VINS ablation
- **WHEN** CARLA data is used in an experiment
- **THEN** the question being answered is one of: (a) does masking reduce ATE, (b) which grade shows VISION_ACTIVE, (c) is the signal object-specific (random_control control)
- **AND** CARLA GT is used only for oracle variants and training labels, never at runtime

#### Scenario: nuScenes misuse is flagged
- **WHEN** an experiment proposes to use nuScenes for VINS ATE evaluation
- **THEN** this SHALL be flagged as role confusion (nuScenes = planner interface evaluation only)
- **AND** the experiment proposal SHALL be rejected until roles are clarified

---

### Requirement: CARLA town classification is fixed — positive candidates vs boundary controls
CARLA towns have a fixed classification in this change. They are not interchangeable.

**Positive urban candidates** (Phase 1–5 search):
- Town01 — reference urban; prior positive signal confirmed
- Town02 — urban mixed; candidate
- Town04 — suburb/urban; candidate
- Town05 — town center + roundabout; candidate
- Town10HD — high-fidelity urban; candidate

**Boundary / negative controls** (Phase 2 confirmed VISION_INERT):
- Town06 — highway; VISION_INERT confirmed (both grades, Phase 2)
- Town07 — rural; VISION_INERT confirmed (both grades, Phase 2)

Town06 and Town07 SHALL NOT be tested as positive candidates again. Their role is to demonstrate that the signal requires urban density and near objects — and that the method does not over-claim in non-urban settings.

#### Scenario: Town06/07 appear in a table
- **WHEN** Town06 or Town07 results appear in a results table
- **THEN** they are in the "boundary / negative control" row or column
- **AND** they are labelled as highway/rural, VISION_INERT, confirmed Phase 2
- **AND** they are not compared head-to-head with urban positive candidates as if equivalent

#### Scenario: New town added as positive candidate
- **WHEN** a new CARLA town not in the list above is proposed as a positive candidate
- **THEN** it requires a change proposal update before it is tested
- **AND** the same R7 preview→core→VINS smoke→vision sensitivity pipeline must be run

---

### Requirement: R7 recordings use condition `dynamic_v3r7`; old data is never overwritten
All new recordings created in this change SHALL use the condition string `dynamic_v3r7`. Recording names follow the pattern `TownXX__dynamic_v3r7__run<scenario>`.

Existing recordings SHALL NOT be overwritten:
- `dynamic_v3` — Town01/Town10HD baseline data
- `dynamic_v3fix` — Town06/07 R6 fix data

#### Scenario: Attempting to overwrite old data
- **WHEN** a recording script would write to a path that matches `dynamic_v3__` or `dynamic_v3fix__`
- **THEN** it SHALL error or refuse, and the user SHALL be alerted
- **AND** the new recording SHALL use `dynamic_v3r7__` in its path

---

### Requirement: VINS-ready classification is strictly defined per recording
A recording is classified as one of: VINS_READY_R7, VINS_UNSTABLE_R7, or NONDETERMINISTIC_R7. This classification is **recording-specific**, not town-specific. A town may have one VINS-ready recording and one unstable recording.

Only VINS_READY_R7 recordings enter vision sensitivity experiments.

VINS_READY_R7 criteria (all must hold):
1. n_vio ≥ 95% of expected (no major tracking failure)
2. no `vins_failures` count > 0
3. no divergence (ATE < 500 m; sanity threshold)
4. ATE rep1 vs rep2 difference < 3%
5. early_scale ∈ [0.85, 1.15]
6. late_scale is repeatable (same direction in rep1 and rep2)

Note: late_scale outside [0.9, 1.1] (e.g., 2.2x as seen in Town06/07) is **NOT** a disqualifier if it is deterministic and repeatable. Scale drift is a known characteristic of single-thread DET2 on highway/rural terrain; it cancels in relative ATE comparisons.

#### Scenario: Recording with deterministic late drift
- **WHEN** a recording has early_scale = 0.997 and late_scale = 2.2 in both rep1 and rep2
- **THEN** it is classified VINS_READY_R7 (drift is deterministic)
- **AND** all subsequent masked experiments use the same ATE baseline (drift cancels in relative Δ%)
- **AND** the late drift is disclosed in all tables

#### Scenario: Recording with nondeterministic ATE
- **WHEN** rep1 ATE = 28 m and rep2 ATE = 52 m (86% difference)
- **THEN** the recording is NONDETERMINISTIC_R7
- **AND** it is excluded from vision sensitivity and TCSV experiments
- **AND** it is reported in the decision document under EXCLUDED

---

### Requirement: Negative results must be reported honestly; no hidden VISION_INERT towns
All towns that complete the vision sensitivity gate must appear in the final decision document, regardless of outcome. A VISION_INERT result is a valid scientific finding (it bounds the claim) and must not be omitted.

The final decision document SHALL include:
- One row per (town, grade, scenario) that completed Phase 3
- Explicit VISION_ACTIVE / VISION_INERT / AMBIGUOUS / UNSTABLE classification
- The signal magnitude (Δ% ATE) and random_control comparison

#### Scenario: All tested towns are VISION_INERT
- **WHEN** Phase 3 completes and all candidate towns are VISION_INERT
- **THEN** the final decision document SHALL state this explicitly
- **AND** the paper claim SHALL be downgraded (planner/perception-facing validity only, no VINS localization contribution)
- **AND** this is reported honestly, not hidden or minimized

#### Scenario: Mixed results — some VISION_ACTIVE, some VISION_INERT
- **WHEN** Town02 is VISION_ACTIVE and Town04 is VISION_INERT under industrial_fog
- **THEN** both results appear in the final table
- **AND** the claim is scoped to VISION_ACTIVE towns only
- **AND** the VISION_INERT towns are noted as negative controls / boundary evidence
