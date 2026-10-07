# Design — shared-object-persistence-orbslam-frontier

## Context (audited facts this design builds on)

- ORB-SLAM3 runs and beats VINS-Fusion on CARLA (stereo-inertial, 2.06 m vs 41.69 m ATE in
  the Phase-6 high-dynamic scene) and runs stereo on KITTI. Wrapper fork
  `~/orbslam_ws/src/orb-slam3-ros2/`; core is vendored, not a submodule.
- No live MapPoint/KeyFrame interface exists. No B4 baseline exists. Frontier stack =
  `wavefront_explorer` (real, built) + stock Nav2 + synthetic BEV scan.
- Detection/tracking = YOLOv8m + ByteTrack + SGBM depth (real, per-det CSV schema exists).
- CARLA data: 469 runs, vehicle NPCs only, `npc_static_frac` gives permanently stopped
  vehicles; no walkers; no stop-and-go flag; one loop recording (loop rejected by ORB-SLAM3).
- Determinism culture from Route C: under machine isolation, runs are bit-identical.

## Decision 1 — Sensor scope is pinned per dataset

CARLA = stereo-inertial (keeps comparability with all existing CARLA results).
KITTI = stereo. No new stereo-only CARLA track is created. This supersedes any earlier
"stereo-only v1" statement.

## Decision 2 — Same binary, flag-gated behavior

All backend modifications live behind a runtime config flag (`object_conditioning: on|off`).
Flag off SHALL be bit-comparable to the unmodified baseline under machine isolation
(Route C protocol). Every core diff is recorded in `orbslam3_core/PATCHES.md` with file,
function, and reason. Diagnostic export is wrapper-first; minimal read-only core accessors
are allowed when the public API is insufficient; behavioral core changes are allowed only
in Gate 4+ and only flag-gated.

## Decision 3 — Coupling mechanism and signal boundary

The coupling chain is `persistence belief → backend anchor state → planner localization
risk`. Two consumer interfaces are separated:

- **Raw object layer** (P2 may use): track id, bbox/mask, depth, velocity, rule dynamic
  probability computed from track kinematics only. P2 localization risk may use only
  object occlusion + vanilla (unlabeled) map-point density.
- **Anchor layer** (P3/P4 only): per-object persistence state, candidate-anchor MapPoint
  support counts, promotion/demotion events, produced by the backend.

P2 consuming the anchor layer invalidates the coupling ablation and is forbidden.

## Decision 4 — Persistence states and rule-based v1

States: `STATIC`, `CANDIDATE_ANCHOR`, `TRANSIENT_OBJECT`, `UNKNOWN`.
Rule persistence v1 (before learning): track stationary duration, velocity variance,
depth stability, track age, with class prior as a weak feature only. Discrete observation
weights: STATIC 1.0, CANDIDATE_ANCHOR 0.3 (sweep 0.3/0.5), UNKNOWN 0.5, TRANSIENT 0.0.

## Decision 5 — Fallback ladder (tracking-time)

Pose optimization uses tiers in strict order, expanding only on starvation:

1. STATIC only;
2. + CANDIDATE_ANCHOR;
3. + UNKNOWN;
4. never TRANSIENT_OBJECT under any tier.

Triggers: tracked inlier count < N_min (default 30, configurable) OR tracked ratio < 0.5
OR pose optimization failure. Hysteresis: a tier expansion persists for ≥ k frames
(default 10) before contraction, to prevent oscillation. The ladder is the runtime
definition of anchor recovery.

## Decision 6 — Candidate anchor demotion

Demotion triggers: sustained track velocity above threshold for k frames, reprojection
residual spike on the object's MapPoints, or geometric inconsistency. On demotion the
object becomes TRANSIENT_OBJECT, its MapPoints are flagged bad for long-term map purposes.
Descriptors already inserted into the loop-closure database are NOT retroactively removed
in v1; residual BoW contamination is measured and reported instead.

## Decision 7 — Label timing / async contract

- Detector runs 5–10 Hz; keypoint labels between detections come from track-state
  interpolation of bbox/mask.
- MapPoint ownership by observation voting: a MapPoint acquires an object label after ≥3
  labeled observations with majority agreement; until then it is UNKNOWN (weight 0.5).
- KeyFrame insertion into the loop-closure (KeyFrame) database is deferred until its object
  labels resolve or a timeout (default 300 ms) elapses, whichever is first; BoW is computed
  once, excluding TRANSIENT descriptors, at insertion time. This requires a small flag-gated
  core hook and is logged in PATCHES.md.
- No global timestamp synchronizer is introduced; per-topic rates remain independent.

## Decision 8 — Frontier utility and exploration deadlock rule

Utility has exactly four terms in v1:

U(f) = w1information_gain(f) - w2path_cost(f)
- w3dynamic_occupancy_risk(f) - w4localization_degradation_risk(f)


- Each term is min-max normalized across the candidate frontier set per replan cycle;
  weights are fixed defaults with a sensitivity sweep in evaluation.
- `localization_degradation_risk` integrates expected visible static / candidate-anchor
  support (raycast from predicted poses along the path) ONLY over path cells whose occupancy
  status is known. The unknown frontier interior contributes information gain only and is
  never penalized for lacking map points.
- Liveness rule: if every candidate frontier exceeds the risk threshold, select the
  minimum-risk frontier instead of stalling.
- Implementation location: `wavefront_explorer` goal scoring. Nav2 planners/controllers
  remain stock. The claim is "localization-risk-aware frontier selection", never
  "a new frontier planner". Injecting risk only via KeepoutFilter / risk bus without
  utility-level consumption is explicitly rejected (that is the costmap-integration
  pattern this change exists to exceed).

## Decision 9 — Learned persistence scope

One learning module only. Per-track temporal model (GRU or temporal CNN; transformer-lite
only if needed). Outputs: `p_static_anchor`, `p_transient`, `p_navigation_blocking`,
`motion_uncertainty`. Inputs: bbox/depth/velocity history, depth stability, position and
velocity variance, track age, object-region ORB feature count, object-region MapPoint
survival, object-region reprojection residual stats, optional compact appearance embedding.
Labels: CARLA GT actor motion over a fixed future horizon (visibility loss is NOT evidence
of motion); KITTI Tracking parked/moving for real-data validation; CARLA oracle persistence
as upper bound. Downgrade rule: if learned does not beat rule persistence on downstream
endpoints, C3 becomes analysis, not a claim.

## Decision 10 — Two-sided gate is the feasibility gate of the paper

The gate requires both failure modes:

- Side A (contamination): in a dense-dynamic suite, B1 degrades on ≥1 localization endpoint
  relative to the best masking variant → culling is needed.
- Side B (starvation): in a low-static-texture + parked-vehicle suite, B3 degrades relative
  to B1 → anchor recovery is needed.
- Rule-anchor (P1-class) must match or beat the best of B1/B3/B4 on both suites.
- B4 is mandatory before any learned-persistence claim; B4 is the strongest reactive
  baseline because geometric checks keep parked vehicles for free. The predictive advantage
  of persistence must be shown on stop-and-go and/or return-visit material, which reactive
  checks cannot handle.

## Decision 11 — Closed-loop strategy

Nav2-in-loop stabilization is a Gate 7 subtask with a timebox; the known ~11.5 s batch exit
must be root-caused or worked around (interactive session protocol acceptable if scripted
reproducibly). The hand-rolled potential-field harness is allowed for development smoke
tests only and never appears as a paper result. Closed-loop CARLA evaluation is mandatory
for the final paper claim.

## Decision 12 — Evaluation discipline

- Coupling gain per endpoint:
  `backend_gain = P1 − B1`, `planner_gain = P2 − B1`, `combined_gain = P3 − B1`,
  `coupling_residual = combined_gain − backend_gain − planner_gain`.
  Reported on primary endpoints (navigation success rate; ATE) and secondary endpoints.
- Integrity metrics (false_safe, availability, unavailable time, HMI-like event count) are
  evaluation metrics only, never utility terms.
- Determinism protocol: CARLA synchronous mode, fixed seeds, machine isolation for
  headline numbers; full matrix on 2 suites × ≥5 seeds; pruned rows elsewhere.
- Loop-closure precision is conditional on resolving the `BAD LOOP!!!` root cause.
- Edge budget table (SLAM 15–25 Hz, detector 5–10 Hz, memory 5–10 Hz, backend update at
  keyframe rate, costmap 5–10 Hz, replan 0.5–2 Hz, control 10–20 Hz) is a planning target;
  dev hardware is a desktop RTX 5090; no edge hardware exists in the project.

## Risks / Trade-offs

- Anchor-recovery gate may fail → C1 weakens to hygiene-only; paper downgrades (accepted
  risk; gate is scheduled early for exactly this reason).
- Deferred loop-DB insertion may interact with LoopClosing timing → flag-gated, measured.
- Stop-and-go recording is new collector work; walkers remain optional to avoid blocking.
- Vendored-core patching without submodule tracking → PATCHES.md discipline mandatory.

## Open Questions

- CANDIDATE_ANCHOR weight 0.3 vs 0.5 (resolved by sweep in Gate 4).
- Whether BoW recompute-on-timeout ever fires in practice (measured in Gate 4).
- Whether KITTI Tracking offers enough parked→moving transitions for learned-persistence
  validation, or nuScenes validity dataset is needed as backup (decide in Gate 6).
