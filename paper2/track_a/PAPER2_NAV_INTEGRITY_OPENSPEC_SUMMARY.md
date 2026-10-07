# Paper-2 — Navigation Integrity Monitoring: OpenSpec Summary

**Change:** `openspec/changes/navigation-integrity-monitoring/`
**Date:** 2026-07-02
**Status:** PROPOSED — validated (`openspec validate --strict` passes). Awaiting Phase 0 (boundary freeze + closed-loop stack audit). No experiments run.

---

## 1. Files created

| File | Purpose |
|---|---|
| `proposal.md` | Problem, architecture, contribution boundary, non-goals, evidence, gates |
| `design.md` | Integrity causal chain, two-independent-channel argument, model I/O, curriculum, reuse, open questions |
| `specs/integrity-formalism/spec.md` | Headline: VIO PL/AL/IR, HMI/false-safe, Stanford diagram, TTA, causal chain |
| `specs/localization-integrity/spec.md` | VINS HealthNet (runtime-only inputs, GT-derived labels, beats rule-based, K0 probe) |
| `specs/obstacle-state-integrity/spec.md` | Obstacle ReliabilityNet (modular source, component decomposition, fixed thresholds, OPL) |
| `specs/navigation-risk-supervisor/spec.md` | Supervisor-on-top boundary, modes, rule-based baseline/fallback, safety-not-speed |
| `specs/fog-fallback-mode/spec.md` | FOG_COAST/STOP_REINIT/UNAVAILABLE, budgets TBD, real-FOG grounding |
| `specs/dataset-label-training/spec.md` | Dataset roles + label producibility, Stage 1–4, pose curriculum P1–P3, no fake data |
| `specs/evaluation-boundary/spec.md` | E1–E4, kill criteria K0–K5, sim-only labelling, isolation discipline |
| `tasks.md` | Gated Phases 0–8 with closed-loop audit early gate + four probes |
| `PAPER2_NAV_INTEGRITY_OPENSPEC_SUMMARY.md` | This file |
| `PAPER2_NAV_INTEGRITY_DATASET_TRAINING_SPEC.md` | Detailed dataset/label/training plan |

## 2. Main title and contribution

**Title:** Learning-based Navigation Integrity Monitoring for GPS-denied Mapless Navigation under Dynamic Obstacles.

**Headline contribution:** an integrity formalism for VIO + obstacle state — a RAIM-style alert-limit / protection-level / integrity-risk framework with two independent integrity channels (localization, obstacle-state) and a Stanford integrity diagram; HMI (false-safe) is the primary failure minimized.

**Main empirical claim:** an integrity-supervisor layer that reduces false-safe / collision / near-miss / missed-risk in closed-loop GPS-denied navigation, without modifying the VINS backend or the Nav2/frontier core planner. Bound to the formalism by one causal chain: `PL ≥ AL → mode switch → fewer HMI/collisions`.

**Not claimed:** a new planner, a modified VINS estimator, a new detector, or a VINS-ATE improvement.

## 3. Reuse of previous project components

| Prior asset | Reused as |
|---|---|
| C1/C2/C3 object validity (CARLA+KITTI, AUROC 0.873/0.924) | Obstacle ReliabilityNet (channel B) — already validated |
| CARLA VINS replay + R7 results | VINS HealthNet positive (drift/degraded) + negative (VISION_INERT clean) cases |
| R7 VISION_INERT finding | Evidence: object density alone ≠ VINS corruption → monitor, don't mask |
| `reliability_features_vins.csv` (~150 col) | VINS HealthNet feature source |
| v4 A2 null (VINS×obstacle weakly coupled) | Justifies two-independent-channel design |
| KAIST FOG/wheel/RTK | VINS HealthNet real training + FOG_COAST feasibility |
| frontier/Nav2 session | Closed-loop evaluation platform (audited Phase 0) |
| grade-conditioned FOG/IMU work | FOG fallback grade physics + drift-budget grounding |

## 4. Dataset / training plan summary

Stage 1 Obstacle ReliabilityNet: nuScenes + KITTI (real) + CARLA (supp.). Stage 2 VINS HealthNet: CARLA replay + KAIST (+ KITTI-raw/EuRoC if feasible), K0-gated. Stage 3 Navigation Risk Supervisor: CARLA/Gazebo closed-loop, frozen A/B, rule-based baseline. Stage 4 integrated fusion: last, only after 1–3. Pose curriculum mandatory: P1 GT teacher → P2 VINS-noise replay → P3 live VINS-in-loop (validation only). All five real datasets physically present at `/mnt/sata4t/datasets/`.

## 5. Simulation-trained vs real-data-trained

- **Real-data:** obstacle reliability (nuScenes, KITTI); VINS health (KAIST, EuRoC, KITTI-oxts); FOG_COAST feasibility (KAIST real FOG).
- **Simulation:** closed-loop episodes, controlled VINS degradation, mode-oracle labels, VINS-noise replay, FOG fallback sim (CARLA/Gazebo).
- **Rule:** any CARLA-only result is labelled simulation-only until a real dataset or the user platform corroborates it (K5).

## 6. Next experiments (gated)

1. Phase 0.3 closed-loop stack audit (pose source, obstacle injection, per-episode logging, P2-before-P3) — the largest dependency for the closed-loop main claim.
2. Phase 2.1 K0 event-count probe — go/no-go for a learned VINS HealthNet.
3. Phase 1.2 obstacle reliability on nuScenes (third real dataset).
4. Phase 6.1 FOG_COAST drift-vs-time curve on KAIST real FOG.

## 7. Claims forbidden until evidence exists

- No learned VINS-health claim until K0 passes and it beats `failureDetection() Bas>2.5` on lead-time + false-safe (CARLA + ≥1 real).
- No closed-loop safety claim until the audited stack logs collision/near-miss/false-safe and the supervisor beats original + rule-based under ≥ P2.
- No learned-supervisor claim unless it beats the rule-based supervisor on held-out towns/routes (else ship rule-based).
- No FOG_COAST benefit claim until the real-FOG drift curve grounds the budget.
- No numeric AL/PL/IR/drift-budget asserted while marked `TBD-XX`.
- No sim-only result stated as a real-world capability. No fabricated/placeholder data.

## 8. Open questions (human decision)

- `TBD-AL-LOC` localization alert limit; `TBD-IR`, `TBD-N` integrity risk + min event count; `TBD-drift-budget`, `TBD-Tmax` FOG_COAST budgets.
- Closed-loop base: keep Nav2/frontier vs add Gazebo-minimal (pending Phase 0 audit cost).
- Venue: T-ITS/T-IV ambition (full closed-loop) vs T-IM/Sensors stable (offline formalism), set by K3/K5.
