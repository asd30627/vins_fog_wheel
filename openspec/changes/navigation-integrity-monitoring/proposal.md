# Proposal — Learning-based Navigation Integrity Monitoring for GPS-denied Mapless Navigation under Dynamic Obstacles

**Change ID:** navigation-integrity-monitoring
**Branch:** grade-fusion-v1
**Date:** 2026-07-02
**Status:** PROPOSED — awaiting Phase 0 (boundary freeze + closed-loop stack audit)

---

## Problem

GPS-denied mapless navigation under dynamic obstacles fails in two orthogonal ways, and today the robot cannot tell either one is happening. First, the visual-inertial estimator (VINS) can silently drift or diverge; the pose looks confident while the true error already exceeds what safe navigation allows. Second, the perceived state of a dynamic obstacle — especially its velocity at range — can be wrong by meters and meters-per-second, yet be fed into time-to-collision (TTC) and motion prediction as if it were trustworthy. When either failure is undetected, the planner produces *hazardously misleading* motion: it drives confidently toward a hazard, or freezes unnecessarily, or reports mission success while unsafe.

Prior work in this repository establishes both failure modes empirically and shows they are **independent**:

- Obstacle-state error is depth-noise-driven. Position error at 30 m+ reaches median 12 m / p95 163 m; velocity error reaches 8–18 m/s (`PAPER2_RAW_OBJECT_BENCHMARK.md`). Position validity and velocity validity fail at different ranges.
- Localization error is motion-observability-driven and orthogonal to obstacle error. Conditioning obstacle reliability on VINS-quality features was tested and found **weakly coupled / redundant** (v4 A2: sensor-frame FAILED, world-frame WEAK). The two are best treated as **independent integrity channels**, not one coupled signal.
- Making dynamic-object masking improve VINS ATE was tested across four urban towns and **failed** (R7: all VISION_INERT, masking < 2% ATE vs a 5% gate). VINS is therefore a backbone to be *monitored*, not a metric to be *won*.

No component in the current stack answers the operationally decisive question: **is it safe to keep navigating right now, and if not, what should the robot do instead?**

## Proposed Change

Introduce a **learning-based navigation integrity monitor** that sits *above* an unchanged VINS backend and an unchanged Nav2/frontier planner, and continuously answers three questions with calibrated, runtime-only signals:

1. **Localization integrity** — is VINS currently unsafe or about to become unsafe (diverging, past its alert limit, needing FOG/IMU fallback)?
2. **Obstacle-state integrity** — is each obstacle's position / velocity / full state reliable enough to act on, or must it be refused/downgraded?
3. **Navigation risk** — given the two channels plus planner context, what risk mode is warranted, and does switching mode reduce collision / near-miss / false-safe / missed-risk?

The headline contribution is an **integrity formalism**: a VINS-and-obstacle analogue of the GNSS RAIM integrity framework (alert limit, protection level, integrity risk, Stanford integrity diagram). Each channel emits a runtime **protection level (PL)** — a statistical bound on its instantaneous error — compared against an **alert limit (AL)**. The decisive failure is *hazardously misleading information* (HMI): PL < AL while the true error ≥ AL (the robot believes it is safe when it is not). The learned monitor's job is to keep HMI (false-safe) rare while keeping availability high, and to drive a risk-mode supervisor that translates integrity into action.

### System architecture (three learned components + one supervisor, two independent channels)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Navigation Integrity Monitor                       │
│                                                                       │
│  Localization Integrity Channel      Obstacle-State Integrity Channel │
│  ┌───────────────────────────┐       ┌────────────────────────────┐  │
│  │ VINS HealthNet            │       │ Obstacle ReliabilityNet    │  │
│  │  → P_vins_unsafe_{now,1s, │       │  → P_{position,velocity,   │  │
│  │     3s}, P_diverging_soon,│       │     full_state}_valid,     │  │
│  │     LPL (loc. prot. level)│       │     OPL (obj. prot. level) │  │
│  └───────────┬───────────────┘       └───────────┬────────────────┘  │
│              │      (independent channels — not feature-concatenated) │
│              └──────────────┬───────────────┬─────┘                   │
│                             ▼               ▼                         │
│                   ┌──────────────────────────────────┐               │
│                   │ Navigation Risk SupervisorNet     │               │
│                   │  + planner/costmap/TTC context    │               │
│                   │  → risk_mode, speed_scale,        │               │
│                   │     fallback_permission           │               │
│                   └──────────────┬───────────────────┘               │
└──────────────────────────────────┼──────────────────────────────────┘
                                    ▼   (supervisory layer only)
        risk_mode ∈ {NORMAL, CAUTION, FOG_COAST, STOP_REINIT, UNAVAILABLE}
                                    │
              ┌─────────────────────┴─────────────────────┐
              ▼                                             ▼
   unchanged VINS backend                     unchanged Nav2 / frontier planner
   (obstacle source is modular:                (speed-gate / mode-trigger / veto,
    YOLO+ByteTrack+stereo | CARLA GT |          no planner-internal modification)
    KITTI/nuScenes GT | LiDAR/depth/costmap)
```

The obstacle source is **modular and detector-agnostic**. Any of {YOLO+ByteTrack+stereo depth, CARLA GT, KITTI/nuScenes GT, LiDAR/depth/costmap} may feed the obstacle channel. The contribution is the **reliability/integrity layer and how navigation uses or degrades obstacle state** — not the detector.

## Title Candidates

1. **Learning-based Navigation Integrity Monitoring for GPS-denied Mapless Navigation under Dynamic Obstacles** (primary)
2. **Protection-Level Monitoring of Localization and Obstacle State for Safe GPS-denied Navigation**
3. **A Two-Channel Integrity Monitor for Visual-Inertial Navigation among Dynamic Obstacles**

## Contribution boundary (main claim)

The main claim is: **an integrity-supervisor layer that reduces false-safe, collision, near-miss, and missed-risk in closed-loop GPS-denied navigation, without modifying the VINS backend or the Nav2/frontier core planner.**

This work does **not** claim: a new planner, a modified VINS estimator, a new object detector, or a VINS-ATE improvement. VINS and the planner are treated as fixed, replaceable black boxes; the closed-loop base (Nav2/frontier) is the current default but is specified as swappable.

## Non-Goals (locked)

- No modification of the Nav2 / frontier core planner. The supervisor acts *on top* (speed-scale, mode-trigger, veto) via published interfaces only.
- No modification of the VINS-Fusion backend. VINS is a monitored, fixed black box; flag-OFF behaviour is bit-identical to baseline.
- No new object detector as a contribution. The obstacle source is a modular, swappable input; no claim depends on a specific detector.
- No claim that dynamic-object masking improves VINS ATE (already falsified; VINS ATE is not a success metric here).
- No end-to-end Transformer as the first model. Modules are trained separately and integrated as frozen, calibrated outputs (Stage 4 is last, gated).
- No navigation training on GT pose only, and no navigation training on live VINS only. The pose curriculum (P1 GT → P2 VINS-noise replay → P3 live-VINS validation) is mandatory.
- No fabricated results. Every reported number comes from a real run on real or simulated data with recorded provenance. No placeholder CSV.
- No sim-only result presented as a real-world claim. CARLA-only findings are labelled CARLA-only until a real dataset (KITTI / nuScenes / KAIST / EuRoC) or the user platform corroborates them.
- No fixed numeric drift budget, integrity risk, or alert limit asserted before it is grounded. Un-grounded numbers are marked `TBD-XX`.

## Evidence status (as of 2026-07-02)

| Claim / component | Status | Source |
|---|---|---|
| Obstacle position vs velocity validity decomposes by range; replicates on real data | **confirmed (CARLA + KITTI)** | C1 in `paper2/track_a`, KITTI 37,022 det |
| Learned obstacle validity beats distance/geometry baselines in-domain | **confirmed** | C2: CARLA AUROC 0.873 vs 0.755; KITTI 0.924 vs 0.686 |
| Refusal reduces overconfident-wrong-velocity | **confirmed** | C3: KITTI 0.544→0.223 |
| Cross-dataset transfer (CARLA→KITTI direct) is weak without target calibration | **confirmed (caveat)** | C2 transfer +0.034 |
| Obstacle and VINS-quality channels are weakly coupled / independent | **confirmed** | v4 A2 (sensor FAILED, world WEAK) |
| Dynamic-object masking improves VINS ATE | **falsified** | R7 all VISION_INERT (< 2% vs 5% gate) |
| VINS HealthNet predicts unsafe/divergence earlier than rule-based | **K0 FIRED (2026-07-02) — learned not viable on current data (~7 scenes, 1 real-sensor, 2 mechanisms); downgraded to rule-calibration** | Phase 2.1 `logs/PHASE2_1_K0_EVENT_PROBE.md` |
| Obstacle OPL + Stanford integrity diagram (obstacle channel) | **CONFIRMED on KITTI** (IR=0.05 calibrated; exceedance 0.068; HMI_among_unsafe 0.09% vs distance-gate 12.5%; 4 Stanford PNGs; reproducible script) | `logs/PHASE1_3_OBSTACLE_OPL_STANFORD.md` |
| Cross-dataset obstacle validity — nuScenes 3rd dataset | **CONFIRMED** (C1 replicates; in-domain AUROC 0.973; calibrated transfer 0.969; direct transfer 0.692) | `logs/PHASE1_2_NUSCENES_VALIDITY.md` |
| Localization LPL + Stanford diagram (localization channel) | **PARTIAL** (CARLA: 0 HMI at IR=0.10/AL=0.20; availability 1.85% — availability crisis pending better runtime signal; KAIST: K0 confirmed, no diagram) | `logs/loc_lpl/` |
| Closed-loop supervisor reduces collision / false-safe | **PARTIAL — blockers** (5-label logger+supervisor node added; goal injection broken; supervisor over-aggressive; batch not run) | `logs/closed_loop/` |
| FOG_COAST keeps drift within budget on real FOG | **not yet measured** | Phase 6 (KAIST drift-vs-time curve) |

## Success gate (change level)

The change succeeds if, at minimum:

1. The integrity formalism is instantiated and both channels produce calibrated PLs with a Stanford integrity diagram on real + sim data (Phase 3).
2. Obstacle ReliabilityNet beats baselines on ≥ 2 real datasets, and VINS HealthNet beats rule-based lead-time on CARLA + ≥ 1 real dataset (Phases 1–2).
3. The closed-loop supervisor reduces collision / near-miss / false-safe versus the original navigation and a rule-based supervisor, under P2 (VINS-noise replay) at minimum (Phase 5).

## Failure gates (per-phase; see `evaluation-boundary` spec K0–K5)

- **K0** — too few localization divergence/alert events in available logs → VINS HealthNet downgraded to a rule-calibration/descriptive result (no learned claim).
- **K3** — supervisor does not reduce collision / near-miss / false-safe in closed-loop → ship the rule-based integrity decision layer only; no navigation-benefit claim.
- **K5** — modules work only in CARLA and fail on real datasets → downgrade venue and narrow claim scope to what real data supports.
