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

### Decision 2 — Grade-conditioning input and training target (design checkpoint — resolved 2026-06-26, awaiting sign-off; gated behind Probes A/B)
The grade-conditioned arbitration was designed at the stop-and-report checkpoint (`DESIGN_CHECKPOINT_2.1.md`), informed by the autonomous 30 s baseline + grade-sweep findings (`AUTONOMOUS_RESULTS.md`, findings B1–B3). Resolved I/O / target:

- **Inputs (runtime-observable only — KAIST deploy has no GT):** (i) FOG **grade indicator** = the Allan parameters `[ARW, bias_instability, BRW]` (normalized; not one-hot → generalizes across the discrete points and supports the KAIST-0.05 alignment point). (ii) **Scene-dynamics signal** `v_dyn2` = the vision-vs-gyro yaw disagreement, computed from an **independent (un-graded) IMU gyro** — never from the graded FOG (well-posedness fix #4). `estimator.cpp` already logs `yaw_resid_med_deg` (visual yaw vs FOG dpsi), so half of `v_dyn2` already exists.
- **Output:** a scalar arbitration coefficient **α ∈ [α_min, α_max]** multiplying the **FOG-yaw factor information** per keyframe (`sqrt_info *= sqrt(α)`; **α≡1 ⇒ bit-identical baseline**). Bounds tied to the oracle grid-search range (never extrapolate beyond explored α).
- **Teacher / training target (revised — direct "who's-right-vs-GT" label, NOT the flat BA-oracle):** per keyframe pair, `Δψ_gt` from GT, `Δψ_fog` from FOG preint, `Δψ_vis` from a **FOG-off vision+IMU rotation** pass (isolates vision's say). `err_fog=|Δψ_fog−Δψ_gt|`, `err_vis=|Δψ_vis−Δψ_gt|`; label α **high** when `err_vis ≫ err_fog`, **low** when `err_fog ≫ err_vis`. The network predicts this from `(grade, v_dyn2)`. This sidesteps the convexity/flatness problem (read off who-is-right, not the bottom of a possibly-flat curve), is far cheaper than per-segment BA grid-search, and is interpretable. The BA grid-search oracle is retained **only as a validation cross-check**, not the primary teacher.
- **GT source:** KAIST real GT pose (the only real FOG anchor, 0.05°/hr) + CARLA GT pose. See Decision 3 for the real-grade-injection that makes the *primary* multi-grade dataset real-scene.
- **Model class (low-capacity, monotone):** a 2-input low-capacity model (monotone schedule / isotonic / shallow tree / discrete-grade lookup), encoding the expected monotonicity (worse grade + higher disagreement → lower α). A flexible NN is rejected — a weak, noisy signal favours a low-variance schedule that generalizes and clears gates; the contribution is "a grade-conditioned arbitration **schedule**, validated and pre-registered", consistent with the discrete-grades / no-continuous-curve stance.
- **Sequence-length regime (forced by finding B1):** grade has ~no effect on 30 s sequences (gyro bias needs time to integrate: precision_mems 5°/hr × 30 s = 0.04°). Train/eval on **≥5 min** sequences; the 120 s-primary choice (Pit 1) is re-examined once the 5-min Curve-1 is in.

#### Open well-posedness checks (each states the cheapest experiment that would prove the decision wrong — pre-registration extended from outcomes to the design itself)
1. **Label identifiability (central).** Some `(grade, dynamics)` buckets may have a flat rotation-error-vs-α curve (Risk: top-grade bias too small; finding B1) → a fitted α* fits noise. → **Probe A** must show an identifiable minimum/curvature in the target buckets; the direct who's-right label is the primary mitigation.
2. **Granularity mismatch.** Constant-α-per-segment label vs per-keyframe network output; when dynamics varies within a segment, best-constant-α ≠ ∫ best-per-keyframe-α. → The chosen who's-right teacher is **per-keyframe-pair**; `v_dyn2` aggregated to match.
3. **Off-policy dynamics proxy.** `v_dyn2` depends on estimator state → on past α (oracle→deploy shift). → Compute `v_dyn2` under the **baseline α≡1 / FOG-off pass**; off-policy caveat acknowledged (α rescales confidence, not the residual target).
4. **Grade × dynamics confound.** If `v_dyn2` used the graded FOG, worse grade inflates the residual even when vision is fine → inputs correlate. → `v_dyn2` from an **independent un-graded gyro**; decorrelation check added to task 0.e.
5. **Translation in do-no-harm.** α changes FOG rotation info → moves translation via joint BA though the *claim* is rotation-only. → Gate 4.3 explicitly checks **translation ATE** does not regress.
6. **Bounds rationale.** α bounds tied to the oracle grid-search range; no extrapolation beyond explored α.

#### De-risking strategy (α is a weak, indirect lever — these raise the probability of a real, gate-passing result)
- **Direct who's-right label over the flat BA-oracle** (above) — biggest lever.
- **Act only inside the identifiable window; abstain (α≡1) elsewhere.** Task-0.e window analysis defines the identifiable region (long segment + real vision-FOG disagreement + GT says FOG is right); train/act on α only there, else α≡1 = baseline. Turns a flat label into *designed abstention* → **do-no-harm nearly free by construction** (cannot harm where it does not act). Default-safe behavior.
- **Low-capacity monotone schedule** over a flexible network.
- **C1 floor.** If learned α only ties baseline, C1 (cross-grade benchmark + anti-cherry-pick framework + the honest "when arbitration helps / when it doesn't" result) still stands and is publishable; a null/below-threshold C2 is a reported finding, not a failure. Removes the "must win to publish" single point of failure.

### Decision 3 — FOG grades are a few discrete Allan-variance points; PRIMARY multi-grade data is real KAIST with injected grades; CARLA is corroboration
No continuous curve. The official list is the four base PROFILES (ideal / military_fog / industrial_fog / precision_mems) plus a KAIST-alignment point (bias=0.05°/hr) and a general-IMU point (~10°/hr), all Allan-variance defined.

- **★Real multi-grade via injection onto KAIST (sim-to-real correction, revised 2026-06-26).** Apply the existing Allan-variance grade injection (the same PROFILES from `carla_dataset_replay_ros2_imu_grade.py`) to KAIST's **real FOG stream**, synthesizing the worse grades on the **real trajectory + real scene + real GT**. This makes the *primary* multi-grade dataset real-scene; sim-to-real then applies only to a well-understood noise-injection model (Allan variance), not to the whole scene/dynamics/trajectory. **CARLA's grade matrix becomes corroboration, not the primary grade anchor.**
- **Why this nearly closes the grade-axis gap:** injection can only *degrade* (add noise), spanning KAIST 0.05 → industrial 0.3 → mems 5 → general 10 — exactly the **mid/low grades where the AI gain is expected to concentrate**. The grades that *cannot* be synthesized on real data (military 0.01, ideal — better than 0.05) are precisely those where FOG bias is too small for α to matter, so the remaining sim-only region is the **least consequential** one.
- The CARLA-fidelity gate (task 5) remains **required** but is no longer the *sole* grade anchor.

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
- **[Risk — well-posedness] Grade × dynamics confound.** If the scene-dynamics input `v_dyn2` were computed from the *graded* FOG, a worse grade would inflate the residual even when vision is fine, correlating the two inputs so `f(grade, dynamics)` cannot separate them. → Mitigation: `v_dyn2` is defined from an **independent un-graded gyro**, and task 0.e adds a grade-vs-dynamics decorrelation check. If they remain correlated, the schedule collapses to grade-only and that is reported.
- **[Risk — well-posedness] Translation leakage in "rotation-only".** Rotation-only is the *claim* scope, but α changes the FOG rotation information and therefore moves translation through joint BA. → Mitigation: the do-no-harm gate (4.3) explicitly checks **translation ATE** does not regress at any grade, not only rotation. A translation regression fails do-no-harm even if rotation improves.
- **[Risk — well-posedness] Flat/ill-posed α label.** In low-grade or low-disagreement buckets the rotation-error-vs-α curve may be flat, so any fitted α fits noise. → Mitigation: the direct who's-right-vs-GT teacher (reads which sensor is closer to GT, not the bottom of a flat curve) + **Probe A** (label-learnability) and **Probe B** (oracle ceiling) gate sign-off; if the oracle ceiling shows no win, stop before training (the user's call).
- **[Trade-off] Engineering cost of Pit 2 (grade+wheel merge) and Pit 3 (player/runner re-wire).** → Accepted, bounded one-time cost; the four known fixes are documented so the re-wire does not re-hit old traps.

## Operating Model (gated execution)

This change is **gated, not a continuous run**. Each phase stops for a human decision. At each gate, STOP and report honestly: pass / below-threshold / fail + the data (per-grade median ATE, spread, effect size) + provenance (binary/onnx md5, commit, data batch, isolation proof). Do NOT push through a gate, re-tune a threshold, or swap sequences/grades unilaterally. The ATE-gate judgment is NOT delegated — it is handed to the user. On any urge to change the direction (the five anchors, the three innovations, the three pits), STOP and ask the user — do not self-decide.

## Open Questions / TODO (fill after the gated tasks run — do not invent)

- Concrete per-grade FOG-base baseline ATE numbers (from the per-grade baseline PRE-TASK).
- The locked win-% threshold (from the baseline run-to-run spread).
- The CARLA-fidelity consistency threshold X% and the calibration-point numbers.
- ~~The grade-conditioning network I/O, training target, and GT source (Decision 2 design checkpoint).~~ RESOLVED 2026-06-26 (Decision 2) — awaiting user sign-off; gated behind Probes A/B (task 2.1 / 2.2).
- The α grid-search range / bounds, and the identifiable-window cut points (filled by Probe A — do not invent).
- The oracle-ceiling win margin per grade and clean-set do-no-harm (filled by Probe B — do not invent).
