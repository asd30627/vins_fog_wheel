## Context

This change pivots the FOG-aided VINS learned-AI program from the **visual-covariance** route (retired; preserved as `openspec/changes/route-c-motion-conditioned-aniso-cov/` for historical/paper evidence) to a **fusion-layer grade-conditioned rotation arbitration**. The AI moves out of the visual-feature weighting layer and into the inertial fusion layer.

**Core theory — two sides of one coin (the user's insight).** "Trusting FOG more = trusting vision less" is one phenomenon viewed two ways. In bundle adjustment all factors compete jointly; raising the FOG information gives FOG more say on rotation, so the relative influence of vision falls out automatically — **without touching the visual factors (which would hit Huber), only by strengthening the FOG side.** This achieves the same "in dynamic scenes, trust vision less" effect while bypassing Huber.

**Honest limitation (must be stated, or reviewers will poke it).** This "strengthen FOG = weaken vision" effect holds **only in the rotation dimension**. FOG measures rotation only; it does not participate in translation. Translation still relies on vision + IMU. But rotation error is the dominant GPS-denied long-range drift source (a small angle error is amplified by distance into a large position drift), so locking down rotation improves position accuracy indirectly but significantly. The paper must mark the scope (rotation) and must not claim a direct visual-downweighting effect on translation.

**Why bypassing Huber works (the technical basis of the whole pivot).** `HuberLoss(1.0)` acts only on the three visual `ProjectionFactor`s (mono/stereo/marg); the FOG yaw factor is NULL loss and the IMU factors are NULL loss. The AI acts on the FOG/IMU side → on the code path it never touches Huber. This is a deliberate architectural choice, and is the reason the previously-fatal structural conflict (continuous visual weighting vs the Huber hard threshold — see PAPER_MATERIAL.md material 1) no longer applies.

## Goals / Non-Goals

**Goals:**
- Add a **grade-conditioned** arbitration of the relative FOG-vs-visual rotation contribution, acting in the inertial fusion layer.
- Prove, across a few discrete FOG grades, how the learned arbitration strategy varies with grade (the Curve-2 finding) in dynamic scenes.
- Keep the deploy env-gated / default-OFF (bit-invariant baseline) and the prior anti-cherry-pick evaluation discipline.
- Isolate the grade effect from visual collapse (Pit 1), merge grade + wheel (Pit 2), and re-wire CARLA→wheel-WS (Pit 3).

**Non-Goals:**
- Outputting any weight or covariance on visual features, or touching the visual `ProjectionFactor`s / Huber (Anchor 2 lock).
- A continuous grade curve — explicitly out of scope; discrete representative grade points only (Innovation 2).
- Claiming a direct visual-downweighting effect on translation (rotation-only scope).
- Using the physical FOG (0.03°/hr) in the primary dataset — it is the final real-vehicle feasibility check only.
- Proving the win now — the AI fusion is not guaranteed to win; bypassing Huber ≠ guaranteed success (pre-registered risk).

## Decisions

### Decision 1 — AI acts in the fusion layer (FOG/IMU information weight), never on visual features
The arbitration conditions the FOG yaw factor / IMU factor information weight (NULL-loss path). It never emits a visual-feature weight/covariance and never touches the visual `ProjectionFactor`s or Huber. This is the Anchor-2 structural lock, motivated by the demonstrated Huber conflict (PAPER_MATERIAL.md material 1); it is locked, not empirical.

### Decision 2 — Grade-conditioning input and training target (stop-and-report before building)
The grade-conditioned arbitration network's inputs (FOG grade indicator + scene-dynamics signal), outputs (the FOG/IMU rotation information weight or arbitration coefficient), training target, and ground-truth source are to be **designed with a stop-and-report checkpoint before implementation** — explicitly to avoid repeating the visual-covariance route's "built before thinking it through" failure. Ground truth comes from KAIST (the only real anchor) plus CARLA precise GT pose. (TODO: the concrete network I/O and target are filled at the design checkpoint — not pre-judged here.)

### Decision 3 — FOG grades are a few discrete Allan-variance points; ground truth only from KAIST (real) + CARLA GT
No continuous curve. The official list is the four base PROFILES (ideal / military_fog / industrial_fog / precision_mems) plus a KAIST-alignment point (bias=0.05°/hr) and a general-IMU point (~10°/hr), all Allan-variance defined. KAIST 0.05°/hr is the only real FOG anchor; CARLA supplies the mid/low grades in simulation with precise GT.

### Decision 4 — Isolate grade from visual collapse via a per-segment health gate (Pit 1, survival-critical)
Grade comparison is admitted by a **per-segment (time-window) visual-health gate**, not a whole-sequence one: a segment is admissible only if the segment-local `ideal_imu` `est_scale ∈ [0.85, 1.15]`; collapsed segments are dropped while the rest of the sequence is kept; 120 s primary, 300 s corroboration. This is forced by the project's own diagnosis (`V21_300S_GRADE_DIAGNOSIS.md`: grade↔bad_union Spearman 0.705; industrial/precision "worse" is often visual scale-collapse; military(0.01) ≈ ideal). Without this isolation the cross-grade curve measures visual collapse, not FOG grade.
**Why per-segment (not whole-sequence):** Innovation 3's selling point is dynamic scenes, which inherently corrupt vision *locally*. A whole-sequence gate would throw away an otherwise-healthy sequence for a local perturbation and could starve the dynamic×healthy data window (the very signal we study). The per-segment gate keeps **local dynamic perturbation** (vision locally corrupted but segment scale healthy = the signal) and drops only **scale collapse** (segment scale leaves `[0.85, 1.15]` = contamination).
**Scope guard (do NOT over-reach):** this refines only the *granularity* of the existing health gate; it does NOT make "degree of visual pollution" a second independent variable (the rejected option C — would inflate scope). Discrete grades, rotation-only, and the no-touch-visual-factors lock (Anchor 2) are unchanged.

### Decision 5 — Merge grade + wheel (Pit 2) and re-wire CARLA→wheel-WS (Pit 3)
The 37G grade matrix is gyro-only; wheel lives in `carla_fwvio`. Grade injection and wheel must be merged. The wheel-WS has no player/runner, so `carla_stereo_player` → wheel-WS `vins_node` + runner must be re-wired with the four known fixes (skip-imu-head 150; R3 det=+1 extrinsic; proper_yref axis transform; new CSV not old parquet). Both are scoped engineering tasks; Pit 3 is stop-and-report.

### Decision 6 — Env-gated default-OFF deploy; isolation rule for all numbers (Decision 10 carried over)
Deploy is env-gated / default-OFF (flag-OFF == baseline, bit-identical under isolation). Run-to-run nondeterminism was root-caused to shared-machine resource contention; under full isolation (CARLA off, no concurrent load) VINS is bit-identical. Therefore all gate/baseline numbers run isolated; CARLA is shut down before any KAIST number.

### Decision 7 — LOSO evaluation; eval-fold vs deployment model
Gate numbers come only from LOSO held-out folds; the all-data model is deployment-only and never a gate claim. (Carried over from the prior change's anti-cherry-pick lock, re-targeted to the cross-grade structure.)

## Risks / Trade-offs (pre-registered — this honesty is a rigor plus)

- **[Risk — survival-critical] CARLA fidelity.** Mid/low grades are fully simulated; the only real anchor is KAIST high-grade (one point). → Mitigation: the CARLA-fidelity calibration gate (align to the KAIST 0.05°/hr point under a defined consistency threshold) + Allan-variance parameters so "grade" is physical. If calibration fails, cross-grade conclusions are not claimed.
- **[Risk] AI fusion is not guaranteed to win.** Bypassing Huber ≠ guaranteed success. → Mitigation: the same gated discipline (do-no-harm, win, LOSO, tiered reporting) — the method is validated, not assumed.
- **[Risk] Top-grade FOG bias may be too small to learn from.** The AI gain may concentrate at the mid/low grades. → This matches the Curve-2 story and is expected up front, not a surprise.
- **[Risk] The two curves may go in opposite directions.** Curve 2 (FOG grade → extra AI gain) has uncertain direction. → This is itself the finding; framed proactively, not hidden.
- **[Risk — Pit 1] Visual-collapse contamination of the grade signal.** Addressed by Decision 4 / the spec REQUIRED per-segment visual-health gate; without it the core argument collapses under the reviewer's second knife.
- **[Risk — dual-contribution honesty] Contribution 1 is not guaranteed either.** The paper is positioned on two parallel contributions (proposal.md: C1 = cross-grade benchmark + anti-cherry-pick framework; C2 = grade-conditioned AI arbitration). The dual structure reduces single-point-of-failure risk but does NOT make C1 a guarantee — C1 still depends on the same preconditions passing: baseline determinism, CARLA fidelity calibration, and Pit-1 per-segment isolation, plus a cross-grade curve that stands up. → Honest framing: C1 is *more likely to hold and less AI-dependent* than C2, but it is not "guaranteed to hold"; writing it as guaranteed would merely move the bet from one hypothesis to another. Both contributions pre-register their preconditions here.
- **[Trade-off] Engineering cost of Pit 2 (grade+wheel merge) and Pit 3 (player/runner re-wire).** → Accepted, bounded one-time cost; the four known fixes are documented so the re-wire does not re-hit old traps.

## Operating Model (gated execution)

This change is **gated, not a continuous run**. Each phase stops for a human decision. At each gate, STOP and report honestly: pass / below-threshold / fail + the data (per-grade median ATE, spread, effect size) + provenance (binary/onnx md5, commit, data batch, isolation proof). Do NOT push through a gate, re-tune a threshold, or swap sequences/grades unilaterally. The ATE-gate judgment is NOT delegated — it is handed to the user. On any urge to change the direction (the five anchors, the three innovations, the three pits), STOP and ask the user — do not self-decide.

## Open Questions / TODO (fill after the gated tasks run — do not invent)

- Concrete per-grade FOG-base baseline ATE numbers (from the per-grade baseline PRE-TASK).
- The locked win-% threshold (from the baseline run-to-run spread).
- The CARLA-fidelity consistency threshold X% and the calibration-point numbers.
- The grade-conditioning network I/O, training target, and GT source (Decision 2 design checkpoint).
