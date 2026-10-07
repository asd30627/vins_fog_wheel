# Explore Session Notes

**Change**: navigation-integrity-monitoring
**Date**: 2026-07-02

## Confirmed Decisions

### D1. Paper-2 pivots to navigation integrity monitoring
Pivot from "TCSV / dynamic object validity for VINS ATE" to "Learning-based Navigation Integrity Monitoring". Driver: the VINS-ATE-masking leg is falsified (R7 all VISION_INERT; gentle_turn late_scale≈2.2 drift buries the <1 m masking signal; the only −14.3% is a single-town lane-placement artifact). VINS is demoted from success metric to a monitored health signal.

### D2. Scope = full stack, closed-loop safety as the main claim
User chose the full integration including closed-loop collision/near-miss/false-safe reduction as the main empirical claim (not deferred to a later paper). Highest venue ceiling (T-ITS ambition), highest risk.

### D3. Headline = integrity formalism
User chose the integrity formalism (VIO protection-level / alert-limit / integrity-risk + Stanford diagram + two-channel monitor) as the headline contribution. Bound to the closed-loop claim via one causal chain: PL ≥ AL → mode switch → fewer HMI/collisions.

### D4. Boundary = supervisor on top; no planner/VINS edit
The supervisor sits above Nav2/frontier and VINS, using published interfaces (speed-scale, mode-trigger, veto) only. No Nav2/frontier core planner modification; no VINS backend modification. Reconciles with the prior frontier red line (frontier not main contribution, don't touch planner/VINS).

### D5. Obstacle source is modular / detector-agnostic
YOLO+ByteTrack+stereo, CARLA GT, KITTI/nuScenes GT, LiDAR/depth/costmap are interchangeable inputs via a common schema. The contribution is the reliability/integrity layer and how navigation uses/degrades obstacle state — not the detector.

### D6. Two independent integrity channels
Localization and obstacle-state integrity are computed independently, not feature-concatenated. Justified by v4 A2 null (VINS-quality × obstacle features weakly coupled/redundant) and by orthogonal error drivers (depth noise vs motion observability). Independence is treated as a feature (RAIM-style independent residuals).

### D7. Closed-loop stack is audited, not assumed
The VINS-in-loop + dynamic-obstacle + collision/near-miss pipeline is NOT assumed complete. Phase 0 audits the existing Nav2/frontier stack (pose source GT/odom/VINS; obstacle injection; per-episode logging; P2-before-P3) as an early gate before scheduling any closed-loop claim.

## Rejected Options (with Reasons)

### X1. De-risked offline-only monitor (closed-loop deferred to Paper-3)
Recommended by the reviewer as the safe core. Rejected by the user in favour of the full-stack closed-loop main claim (D2).

### X2. Obstacle-reliability as the headline
Rejected in favour of the integrity formalism (D3); obstacle reliability remains a validated pillar, not the headline.

### X3. VINS-quality-conditioned obstacle reliability (v4 A2)
Rejected earlier by evidence (sensor-frame FAILED, world-frame WEAK). Superseded by two-independent-channel design (D6).

### X4. Dynamic-object masking to improve VINS ATE
Rejected by evidence (R7 all VISION_INERT). VINS ATE is not a success metric for this change.

### X5. End-to-end Transformer first
Rejected: modules trained separately and integrated as frozen calibrated outputs; Stage 4 fusion is last and gated.

## Future Change Drafts

- Integrated temporal fusion (Stage 4) may become its own change if module-level results warrant.
- FOG_COAST budget grounding may spin off shared numbers with `grade-conditioned-inertial-fusion`.

## Unresolved Issues

- `TBD-AL-LOC`, `TBD-IR`, `TBD-N`, `TBD-drift-budget`, `TBD-Tmax` — grounded in Phases 2/6.
- Closed-loop base decision (Nav2/frontier vs Gazebo-minimal) — pending Phase 0 audit cost.
- Venue target — set by K3/K5 outcomes.

## Scope Confirmation for Current Change

Confirmed: full-stack integrity monitor, integrity formalism headline, closed-loop safety main claim, supervisor-on-top boundary, modular obstacle source, closed-loop stack audited as early gate. Spec files created and validated (`openspec validate --strict` passes). Awaiting user go-ahead to begin Phase 0.
