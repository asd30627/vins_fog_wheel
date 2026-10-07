# Design — Navigation Integrity Monitoring

**Change ID:** navigation-integrity-monitoring
**Date:** 2026-07-02
**Status:** Design draft — gated behind Phase 0 audit + Phase 2 K0 probe before any training claim.

---

## 1. Central design decision: one causal chain, two independent channels

The headline (integrity formalism) and the main claim (closed-loop safety) are bound into a **single causal chain** so a reviewer needs to believe one story, not two:

```
protection level (PL)  ─►  PL ≥ alert limit (AL)  ─►  risk_mode switch  ─►  fewer HMI / collisions
   [formalism]              [detection event]         [supervisor action]    [closed-loop result]
```

The monitor computes a per-channel PL, compares it to a per-channel AL, and the decisive metric is **HMI (hazardously misleading information) = false-safe**: PL < AL while true error ≥ AL. Closed-loop experiments exist to prove the formalism keeps HMI rare in the loop, not as a separate contribution.

The two channels are **independent by evidence, and this independence is a feature**:

| Channel | Failure driver | Evidence it is independent of the other |
|---|---|---|
| Localization Integrity (VINS HealthNet) | motion observability, inertial bias, feature geometry | v4 A2: conditioning obstacle reliability on VINS features FAILED/WEAK |
| Obstacle-State Integrity (Obstacle ReliabilityNet) | stereo/mono depth noise, track age, bearing observability | Obstacle error is depth-driven, orthogonal to VINS ATE |

Treating them as two orthogonal integrity channels (like independent GNSS residuals in RAIM) is cleaner than forcing a coupling the data rejected. The supervisor combines two calibrated risk sources; it does not re-derive one from the other.

## 2. Integrity formalism (headline)

Reuse the GNSS/RAIM integrity vocabulary, instantiated for VIO and obstacle state. All numeric bounds start as `TBD-XX` and are grounded in Phase 1–3.

| Term | Symbol | Meaning in this work | Grounding |
|---|---|---|---|
| Alert Limit | AL | Max true error tolerable for safe navigation, per channel | Localization AL: `TBD-AL-LOC` (position/heading bound). Obstacle AL: position 3 m, velocity 3 m/s (reuse existing labels). |
| Protection Level | PL | Runtime statistical bound s.t. P(true error > PL) ≤ integrity risk | Learned + calibrated (isotonic/conformal). LPL (localization), OPL (obstacle). |
| Integrity Risk | IR | Target probability of undetected unsafe (HMI) per decision/window | `TBD-IR` (start from an operational target; report sensitivity). |
| Time-to-Alert | TTA | Lead time between PL≥AL and true-error≥AL | Measured, not assumed. |
| Stanford integrity diagram | — | PL (y) vs true error (x); quadrants nominal / available / MI / HMI | Primary evaluation figure per channel. |

Integrity events (per channel, per window):

- **Nominal / safe**: true error < AL and PL < AL.
- **Correct alert**: true error ≥ AL and PL ≥ AL (system warns and is right).
- **False alert (availability cost)**: true error < AL but PL ≥ AL (over-conservative).
- **HMI / false-safe (the failure to minimize)**: true error ≥ AL but PL < AL.

## 3. Model A — VINS HealthNet (localization integrity channel)

**Purpose.** Predict whether VINS is unsafe now or will be soon, and emit LPL.

**Inputs (runtime-only; from VINS replay/logs, never GT).** feature_count; feature survival ratio; reprojection residual stats; outlier ratio; keyframe rate; solver iteration count; IMU residual proxy; bias jump proxy (`Bas`, `Bgs` deltas); velocity jump; yaw-rate inconsistency (vision-vs-gyro); image blur / low-texture score; dynamic-object feature ratio (if the obstacle channel is available); reset / tracking-lost flag. Source: existing `reliability_features_vins.csv` (~150 columns) + VINS replay metrics (`paper2_vins_metrics.py`).

**Outputs.** `P_vins_unsafe_now`, `P_vins_unsafe_in_1s`, `P_vins_unsafe_in_3s`, `P_diverging_soon`, `P_last_state_trustworthy`, `LPL` (localization protection level), optional `time_to_alert_est`.

**Labels (require GT pose; available in CARLA/KAIST-RTK/EuRoC-Vicon/KITTI-oxts).** `unsafe_now = 1[pose_error ≥ AL_loc]`; `unsafe_in_{1,3}s = 1[unsafe within horizon]`; `diverging_soon = 1[future error slope > threshold]`; `last_safe_time = latest t before unsafe with error < AL`; plus estimator-emitted reset/tracking-lost/incomplete-trajectory flags.

**Baselines it MUST beat (K2).** feature-count threshold; reprojection-residual threshold; outlier-ratio threshold; VINS internal `failureDetection()` (`Bas > 2.5`) as an alert source; a rule-based health monitor combining the above.

**Design risk (K0).** Clean isolated VINS runs do not diverge (bit-deterministic; KAIST survival is acc-bias-driven and grade-invariant). The number of genuine divergence/alert events in available logs is unknown and may be too small to train/evaluate a learned model with statistical power. Phase 2 begins with an **event-count probe**: count distinct alert-limit-exceeded / divergence episodes across CARLA R7 drift, degraded Town06/07, grade-injected KAIST, EuRoC. If below `TBD-N` distinct episodes, K0 downgrades HealthNet to descriptive/rule-calibration.

## 4. Model B — Obstacle ReliabilityNet (obstacle-state integrity channel)

**Purpose.** Predict whether each obstacle's position/velocity/full-state is reliable, and emit OPL. Detector-agnostic.

**Inputs (runtime-only, per-object track sequence).** bbox x,y,w,h; bbox area / area change; detection confidence; class; depth/range/bearing; track age; missed count; raw speed; constant-velocity residual; acceleration/jerk score; direction-flip count; depth/bbox/position/velocity jitter; occlusion proxy. Temporal features via fixed-window pooling (W=5 optimal in prior work); deep sequence models are not used (GRU/TCN/Transformer underperformed pooling).

**Outputs.** `P_position_valid`, `P_velocity_valid`, `P_full_state_valid`, `sigma_position`, `sigma_velocity`, `OPL_{position,velocity}`.

**Labels (ego-independent, thresholds fixed before evaluation).** `position_valid = 1[position_error ≤ 3 m]`; `velocity_valid = 1[velocity_error ≤ 3 m/s]` (optionally AND `dir_err ≤ 45°`); `full_state_valid = position_valid AND velocity_valid`. Thresholds documented and frozen; ablations reported but never re-tuned per dataset after results.

**Status.** Largely done (C1/C2/C3) on CARLA + KITTI. Phase 1 extends to nuScenes and adds OPL calibration. The open risk is cross-dataset generalization without target calibration (C2 transfer was weak).

## 5. Model C — Navigation Risk SupervisorNet + Mode Supervisor

**Purpose.** From the two frozen calibrated channels + planner context, predict navigation risk and select a risk mode.

**Inputs.** frozen HealthNet outputs (incl. LPL); frozen ReliabilityNet outputs (incl. OPL); min obstacle distance; min TTC; local costmap density; frontier distance; planner valid/invalid signal; cmd_vel; oscillation/stuck proxy; emergency-stop flag; current mode.

**Outputs.** `P_collision_or_near_miss`, `P_freezing`, `P_unnecessary_stop`, `risk_mode`, `recommended_speed_scale`, `fallback_permission`.

**Labels (from closed-loop episodes).** collision; near_miss; freezing; unnecessary_stop; mission_success; false_safe; missed_risk; `mode_oracle` (best mode in hindsight given GT).

**Mode definitions.**

| Mode | Trigger (informal) |
|---|---|
| NORMAL | localization safe, obstacle risk low, planner healthy |
| CAUTION | localization or obstacle risk elevated → reduce speed, enlarge margin, continue carefully |
| FOG_COAST | localization unsafe/diverging, `last_safe_time` exists, FOG/IMU propagation within drift budget, navigation risk low enough to continue slowly |
| STOP_REINIT | localization unsafe, FOG uncertainty over budget OR obstacle risk too high → stop and attempt VINS reinit |
| UNAVAILABLE | cannot guarantee localization or navigation safety → fail safe / stop mission |

**Design risk (K3, "learned imitates its own oracle").** The mode-oracle is a hand-designed policy; a learned supervisor may not beat the rule-based version of the same oracle. Mitigation: a rule-based supervisor built from the calibrated channels is the *baseline and the fallback deliverable*. The learned supervisor is claimed only if it beats rule-based on held-out closed-loop episodes with genuine generalization (new towns/routes). If not, ship the rule-based integrity decision layer (still a valid contribution) and drop the learned-supervisor claim.

**Boundary (locked).** The supervisor acts on top of the planner via speed-scale / mode-trigger / veto through published interfaces. It never edits the Nav2/frontier planner internals and never edits the VINS backend.

## 6. FOG_COAST / STOP_REINIT — fallback design

FOG fallback is not the contribution by itself; the contribution is **learning when to switch, which mode, how early, and how much false-safe/missed-risk drops**. Design commitments:

- FOG_COAST allowed only when: localization unsafe/diverging AND `last_safe_time` exists AND FOG/IMU propagation drift from `last_safe_time` to now ≤ drift budget AND navigation risk low enough AND expected fallback duration ≤ `T_max`.
- STOP_REINIT when: localization unsafe AND (FOG uncertainty > budget OR obstacle/navigation risk too high OR VINS cannot recover while moving).
- UNAVAILABLE when: VINS cannot recover AND FOG uncertainty too high AND planner cannot guarantee safety.
- Drift budget, `T_max`, and integrity risk are `TBD` until grounded by the Phase 6 KAIST drift-vs-time curve (real navigation-grade FOG, 0.05°/hr). Grade physics from the sibling `grade-conditioned-inertial-fusion` work applies: grade effects need ≥ minutes to integrate, so short coasts on navigation-grade FOG are the feasible regime.

## 7. Training curriculum (modules first, integration last)

| Stage | Model | Trained on | Note |
|---|---|---|---|
| 1 | Obstacle ReliabilityNet | nuScenes + KITTI (real) + CARLA (supplementary) | pooling HistGBM/XGBoost/monotone; deep seq models are negative ROI |
| 2 | VINS HealthNet | CARLA VINS replay + KAIST (+ KITTI-raw/EuRoC if feasible) | gated by K0 event-count probe |
| 3 | Navigation Risk Supervisor | CARLA/Gazebo closed-loop; GT-pose teacher + VINS-noise replay; frozen A,B outputs | rule-based baseline mandatory |
| 4 | Integrated temporal fusion | multi-task heads over sequence of A/B/context embeddings | only after Stages 1–3 work; not first |

**Pose curriculum (mandatory).** P1 GT/oracle pose (teacher policy, clean navigation risk) → P2 VINS-noise replay (inject realistic drift/scale/yaw/delay/reset/jump from VINS replay logs) → P3 live VINS-in-loop (validation only, not the first/primary training source). Navigation is never trained on GT-only nor on live-VINS-only.

## 8. Closed-loop stack — audited, not assumed (Phase 0 early gate)

The closed-loop VINS-in-loop + dynamic-obstacle + collision/near-miss pipeline is **not assumed complete**. Phase 0 audits the existing Nav2/frontier stack and answers, before any closed-loop claim is scheduled:

1. Does navigation currently run on GT pose, odom, or VINS pose?
2. Can dynamic obstacles be injected into the closed-loop scenario?
3. Can the stack log collision, near_miss, freezing, mission_success, false_safe per episode?
4. Can it run VINS-noise replay (P2) before live VINS-in-loop (P3)?

Nav2/frontier is the default closed-loop base but is specified as swappable; if bring-up cost is prohibitive, an alternative closed-loop base (e.g., Gazebo minimal) may substitute. The audit output gates whether Phase 4/5 proceed or the closed-loop leg is descoped for this change.

## 9. Reuse of prior work

| Prior asset | Role here |
|---|---|
| C1/C2/C3 object validity (CARLA+KITTI) | Obstacle ReliabilityNet (channel B), already validated |
| CARLA VINS replay / R7 results | VINS HealthNet positive (drift/degraded) and negative (VISION_INERT clean) cases |
| R7 VISION_INERT finding | Evidence that object density alone ≠ VINS corruption; motivates monitoring over masking |
| `reliability_features_vins.csv` (~150 col) | VINS HealthNet feature source |
| KAIST FOG/wheel/RTK | VINS HealthNet real training + FOG_COAST feasibility |
| frontier/Nav2 session | Closed-loop evaluation platform (audited in Phase 0) |
| grade-conditioned FOG/IMU work | FOG fallback grade physics + drift budget grounding |

## 10. Open questions (human decision required)

- `TBD-AL-LOC`: localization alert limit (position/heading) for "unsafe" — operational target vs derived from planner safety margin.
- `TBD-IR` / `TBD-N`: target integrity risk and minimum event count for a learned HealthNet claim.
- `TBD-drift-budget`, `T_max`: FOG_COAST budgets — pending Phase 6 real-FOG curve.
- Closed-loop base: keep Nav2/frontier vs add Gazebo minimal — pending Phase 0 audit cost.
- Venue: T-ITS/T-IV ambition (full closed-loop) vs T-IM/Sensors stable (offline formalism) — pending K3/K5 outcomes.
