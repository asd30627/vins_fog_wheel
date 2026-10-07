# Proposal: Shared Object Persistence Memory for Coupled ORB-SLAM3 Backend and Prior-Map-Free Frontier Navigation

## Why

Prior-map-free / GPS-denied navigation in dynamic environments requires both robust
localization and traversability-aware exploration. Existing dynamic-SLAM methods treat
dynamic objects as outliers to remove (class-prior masking, geometric consistency checks);
existing exploration planners treat objects only as occupancy cost. Neither couples the two.

The publishable claim of this change:

> A per-object persistence / anchor belief maintained in a shared object memory is consumed
> by the ORB-SLAM3 backend for MapPoint lifecycle, tracking-time exclusion, candidate-anchor
> recovery, and loop-closure hygiene; the backend-produced candidate-anchor / static support
> is in turn consumed by frontier selection as a localization-risk signal. Unlike masking
> methods that remove all movable-class features, the system rejects transient points while
> recovering persistent candidate anchors under feature starvation. The system is evaluated
> under closed-loop prior-map-free CARLA navigation and offline KITTI Tracking, with
> localization, navigation, and integrity metrics.

The coupling chain is directional and explicit:
`persistence belief → backend anchor state → frontier localization risk`.
A paper where two subsystems independently consume raw detections is system integration;
a paper where the planner consumes backend-derived anchor support, with a measured
coupling residual, is a contribution.

## Relation to Standing Rulings

- The PI ruling of 2026-07-02 (focus OPL paper, no new branches) and the frontier red line
  of 2026-06-30 (frontier is downstream demo; do not modify planner; do not touch VINS
  backend) remain in force for the VINS / Paper-2 OPL line.
- The user has explicitly ruled this change as an **authorized exception**: it modifies the
  ORB-SLAM3 backend (never VINS) and the frontier goal-scoring layer (never the Nav2
  planning/control stack), inside this change only.
- The OPL paper line proceeds in parallel and is unaffected by this change.

## What Changes

- **New capability `object-persistence-memory`**: a shared per-track store with persistence
  states (STATIC / CANDIDATE_ANCHOR / TRANSIENT_OBJECT / UNKNOWN), rule-based persistence
  first, learned persistence later, an explicit label-timing/async contract, and two
  separated consumer interfaces (raw object layer vs backend-derived anchor layer).
- **New capability `orbslam3-object-backend`**: flag-gated modifications to the ORB-SLAM3
  stack — diagnostic export first (wrapper publisher, minimal read-only core accessors),
  then frame-level transient exclusion with a fallback ladder, transient MapPoint lifecycle,
  candidate-anchor promotion/demotion, BoW / loop-closure hygiene, optional three-level
  Local BA weighting. All core diffs logged in `orbslam3_core/PATCHES.md`; flag off must be
  bit-comparable to baseline.
- **New capability `localization-risk-frontier`**: frontier utility with exactly four terms
  (information gain, path cost, dynamic occupancy risk, localization degradation risk),
  computed in `wavefront_explorer` goal scoring. Localization risk is evaluated only on the
  known traversal segment; the unknown frontier interior is never penalized (exploration
  deadlock rule). The utility explicitly consumes backend anchor support in the coupled
  configuration.
- **New capability `evaluation-protocol`**: two-sided anchor-recovery gate (B1 contamination
  failure + B3 starvation failure), mandatory B4 geometric/optical-flow baseline, ablation
  matrix B1–B5 / P1–P7, coupling-gain definition, three metric families (localization,
  navigation, integrity), determinism protocol, and Edge-AI budget as planning targets only.

## Known Gaps Carried From Repo Audit (v3, 2026-07-02)

1. ORB-SLAM3 wrapper has **no** live MapPoint / KeyFrame / keypoint-observation interface
   (only pose→TUM file + shutdown trajectory dump). This is the largest single gap.
2. B4 geometric / optical-flow dynamic mask baseline does not exist in any form.
3. `paper2_validity_bridge` is a risk bus, not a candidate-anchor store; Nav2 costmaps run
   stock defaults; occupancy input is a synthetic BEV LaserScan, not a project-owned grid.
4. Closed-loop Nav2-in-loop is not stable (full `navigation_launch` exits ~11.5 s in batch
   mode; prior A/B results bypassed Nav2 with a hand-rolled controller).
5. CARLA recordings contain no pedestrians/walkers and no explicit stop-and-go flag; one
   return-visit recording exists but ORB-SLAM3 rejected the loop (`BAD LOOP!!!`, root cause
   unresolved).
6. Edge-AI numbers have no measurement basis (dev machine is a desktop RTX 5090); all rate
   budgets in this change are planning targets.
7. ORB-SLAM3 shutdown global-BA hang forces SIGKILL in all existing scripts.

## Impact

- Affected workspaces: `~/orbslam_ws` (wrapper + flag-gated core patches),
  `~/nav2_ws` (`wavefront_explorer`, new anchor-store node beside `paper2_validity_bridge`),
  `~/fwvio_ws` (collector: one new stop-and-go recording type).
- Explicitly NOT affected: VINS-Fusion (zero changes), OPL paper line, Nav2 planning and
  control plugins (stock retained).
- New specs: `object-persistence-memory`, `orbslam3-object-backend`,
  `localization-risk-frontier`, `evaluation-protocol`.
- Compute impact: full ablation matrix restricted to 2 scenario suites × ≥5 seeds; all other
  suites run a pruned row set (B1/B3/B4/P3/P4).

## Non-Goals (first publishable version)

- Full moving-object state nodes / dynamic object factor graph inside ORB-SLAM3 BA.
- Learned pose correction, learned depth, learned descriptors, continuous learned feature
  weighting, RL frontier policy.
- New detection / tracking / frontier algorithms as claims.
- Multi-session / lifelong mapping claims (return-visit scenarios are within-session).
- Real-vehicle closed loop (qualitative demo at most).
- Retroactive BoW cleanup after anchor demotion (measured as residual contamination instead).
- p_loop_closure_safe as a separate learned head (high p_static_anchor threshold instead).
