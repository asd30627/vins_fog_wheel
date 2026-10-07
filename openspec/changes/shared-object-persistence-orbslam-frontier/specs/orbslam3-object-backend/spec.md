## ADDED Requirements

### Requirement: Flag-gated modification with bit-comparable baseline
All object-conditioned backend behavior SHALL be gated by a runtime configuration flag in a
single binary; with the flag off, trajectory output SHALL be bit-comparable to the
unmodified baseline under the machine-isolation determinism protocol; every core source
modification SHALL be logged in `orbslam3_core/PATCHES.md`.

#### Scenario: Flag off equals baseline
- **WHEN** the same sequence is run twice on an isolated machine, once with the unmodified
  baseline and once with the modified binary with `object_conditioning: off`
- **THEN** the TUM trajectory outputs SHALL be bit-identical

### Requirement: Per-keyframe diagnostic export
The wrapper SHALL publish per-keyframe diagnostics (keyframe id, pose, keypoints, MapPoint
ids/positions/observation links) sufficient for offline object association; read-only core
accessors MAY be added when the public API is insufficient; the export SHALL NOT alter
estimation behavior.

#### Scenario: Export without behavior change
- **WHEN** diagnostic export is enabled on an isolated run
- **THEN** the trajectory output SHALL remain bit-identical to the run with export disabled

### Requirement: Frame-level transient exclusion with fallback ladder
Pose optimization SHALL use observation tiers in strict order — STATIC only; then
+CANDIDATE_ANCHOR; then +UNKNOWN; never TRANSIENT_OBJECT — expanding a tier only when
tracked inlier count or tracked ratio falls below configured thresholds or pose
optimization fails, with hysteresis of at least k frames before contraction.

#### Scenario: Starvation triggers recovery
- **WHEN** tracked inliers using STATIC-only observations fall below N_min
- **THEN** the tracker SHALL expand to include CANDIDATE_ANCHOR observations before
  considering UNKNOWN, and SHALL never include TRANSIENT_OBJECT observations

#### Scenario: Hysteresis
- **WHEN** a tier expansion has occurred
- **THEN** the tier SHALL NOT contract for at least k frames even if inlier counts recover

### Requirement: Transient MapPoint lifecycle
MapPoints owned by TRANSIENT_OBJECT tracks SHALL NOT be inserted into the long-term map and
SHALL be culled on an accelerated schedule; UNKNOWN MapPoints SHALL follow default lifecycle
at UNKNOWN weight.

#### Scenario: Transient point exclusion
- **WHEN** a MapPoint's ownership resolves to TRANSIENT_OBJECT
- **THEN** it SHALL be excluded from long-term map insertion and scheduled for accelerated
  culling

### Requirement: Candidate anchor promotion and demotion
Object tracks meeting persistence criteria SHALL be promoted to CANDIDATE_ANCHOR with
discrete observation weight (0.3 or 0.5, configurable); on sustained motion, residual
spike, or geometric inconsistency the track SHALL be demoted to TRANSIENT_OBJECT and its
MapPoints flagged bad; descriptors already inserted into the loop-closure database SHALL
NOT be retroactively removed in v1, and residual BoW contamination SHALL be measured and
reported.

#### Scenario: Demotion on departure
- **WHEN** a CANDIDATE_ANCHOR track exhibits sustained velocity above threshold for k frames
- **THEN** the track SHALL be demoted to TRANSIENT_OBJECT and its MapPoints excluded from
  further long-term use, while prior BoW entries remain and are counted as residual
  contamination

### Requirement: BoW and loop-closure hygiene with deferred insertion
KeyFrame insertion into the loop-closure database SHALL be deferred until object labels
resolve or a configurable timeout (default 300 ms) elapses; BoW SHALL be computed excluding
TRANSIENT_OBJECT descriptors at insertion time; the frequency of timeout-path insertions
SHALL be measured.

#### Scenario: Deferred insertion
- **WHEN** a new KeyFrame is created before its detector labels arrive
- **THEN** its loop-database insertion SHALL wait for label resolution up to the timeout,
  and its BoW SHALL exclude descriptors labeled TRANSIENT_OBJECT at insertion time
