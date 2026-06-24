> **Gated execution.** Every phase is gated: STOP and report (pass / below-threshold / fail + data + provenance), do NOT push through, do NOT re-tune thresholds or swap sequences/grades. **The ATE-gate judgment is NOT delegated — it is handed to the user.** On any urge to change the direction (five anchors / three innovations / three pits), STOP and ask the user.

## 0. PRE-TASK — Take over the existing grade infrastructure + resolve the three pits (CARLA already investigated 2026-06-25; facts confirmed, do not re-investigate)

- [ ] 0.a **Assemble the official grade list.** Confirmed: the 4 Allan-parameterised PROFILES already exist in `carla_dataset_replay_ros2_imu_grade.py` (ideal_imu / military_fog 0.01°/hr / industrial_fog 0.3 / precision_mems 5.0). Add the KAIST-alignment point (bias=0.05°/hr) and the general-IMU point (~10°/hr), and record the finalised list as the spec's official grade set. **[Verification]** Note the counter-intuitive naming (precision_mems is the WORST, 5°/hr); ordering by bias only. **[Continuity]** Confirmed 37G long-sequence asset: `/mnt/sata4t/datasets/carla_vins/v21_300s_grade_matrix` (3 cities × 2 weather × 4 grades × 4 seeds, ~310 s each; 120 s / 600 s variants also exist).
- [ ] 0.b **Resolve Pit 1 (survival-critical) — write the visual-health admission constraint.** Encode the spec REQUIRED: grade comparison admitted only when `ideal_imu` is healthy (`est_scale ∈ [0.85, 1.15]`); 120 s primary (confirmed 6/6 ideal healthy), 300 s corroboration only; exclude any sequence where `ideal_imu` itself collapses. **[Verification]** Cross-check against `V21_300S_GRADE_DIAGNOSIS.md` (grade↔bad_union Spearman 0.705; military(0.01)≈ideal). This is the core-argument survival key.
- [ ] 0.c **Resolve Pit 2 — merge grade injection with wheel.** The 37G grade matrix is gyro-only; wheel lives in `carla_fwvio` (new CSV pipeline, wheel + synth FOG). Wire grade injection into the wheel-carrying pipeline (or add wheel to the grade matrix) so each sequence carries grade-injected gyro AND wheel. **[Verification]** Assert both channels present per sequence.
- [ ] 0.d **Resolve Pit 3 — re-wire CARLA→wheel-WS, apply the four known fixes (STOP-AND-REPORT).** Wire `carla_stereo_player` → wheel-WS `vins_node` + a CARLA runner. Apply: (1) `--skip-imu-head 150`; (2) R3 extrinsic `[[0,0,1],[0,1,0],[-1,0,0]]` (det=+1); (3) `proper_yref` axis transform (accel `(ax,−ay,az)`, gyro `(−wx,wy,−wz)`); (4) new CSV pipeline, NOT the old `sigma_uv=0` parquet. **[Verification]** Confirm VINS emits a full trajectory (not ~1 row) and scale ≈ 1.0 (not 7.5× escape). Solutions recorded in PAPER_MATERIAL.md. STOP and report.

## 1. Baseline — per-grade FOG-base (no AI) on KAIST + CARLA; measure determinism; draw Curve 1

- [ ] 1.1 Run FOG-base (no AI) per grade on KAIST and CARLA, **multi-rep, isolated** (CARLA off when measuring KAIST; no concurrent load). **[Verification]** Record per-grade median ATE + run-to-run spread + provenance (binary md5, commit, isolation proof). (TODO: fill the concrete per-grade ATE numbers — do not invent.)
- [ ] 1.2 **Fix the win-% threshold** from the measured baseline spread, and lock it into the win gate (task 4) and the spec. **[Compliance]** Once locked, do not change mid-evaluation.
- [ ] 1.3 Draw **Curve 1 (FOG grade → ATE)** from visually-healthy data only (Pit 1 admission). **[Conflict]** Exclude any grade point measured on a visually-collapsed sequence; report which sequences were admitted/excluded. STOP and report.

## 2. AI-fusion architecture design (grade-conditioned rotation arbitration) — design checkpoint, stop-and-report

- [ ] 2.1 Design the grade-conditioned arbitration network: inputs (FOG grade indicator + scene-dynamics signal), output (FOG/IMU rotation information weight / arbitration coefficient), training target, and GT source (KAIST real + CARLA GT). **[Compliance]** Acts in the fusion layer only (FOG/IMU information weight); never emits a visual-feature weight; never touches the visual `ProjectionFactor`s or Huber (Anchor 2 / Decision 1). **[Audience]** Present the full design for user sign-off BEFORE any implementation — explicitly to avoid the visual-covariance route's "built before thinking it through" failure. STOP and report.

## 3. Implementation — env-gated, default-OFF

- [ ] 3.1 Implement the grade-conditioned arbitration at the FOG yaw factor / IMU factor information-weighting point. **[Compliance]** Env-gated, default-OFF; with the flag OFF the path is bit-identical to baseline. No change to visual factors / Huber.
- [ ] 3.2 Verify flag-OFF bit-invariance under isolation (VIO md5 + row count unchanged vs pre-change baseline). **[Verification]** Record before/after md5; isolation required (CARLA off, no concurrent load).

## 4. Train + cross-grade evaluation (LOSO held-out, gated)

- [ ] 4.1 **[LOSO split design — USER-REVIEW GATE before any training]** Produce the explicit LOSO fold table (respecting the cross-grade structure) and present for user sign-off. **[Compliance]** Gate numbers come ONLY from held-out folds; the all-data model is deployment-only and never a gate claim.
- [ ] 4.2 Train per LOSO fold + one all-data deployment-only model. **[Compliance]** Label the deployment model deployment-only.
- [ ] 4.3 **Do-no-harm gate (hard):** FOG-base vs FOG+AI-fusion on the full clean set, per grade, multi-rep, isolated. **[Compliance]** Pass iff no grade's clean sequence reproducibly worsens. Provenance on every number. STOP and report.
- [ ] 4.4 **Win gate (dynamic):** FOG-base vs FOG+AI-fusion on the dynamic set across grades, multi-rep, isolated. Each gate ATE from its LOSO held-out fold (never the deployment model). **[Compliance]** Pass iff the locked-threshold reduction is met AND the gain is direction-consistent across grades. Report Curve 1 and Curve 2 separately. **Tiered honesty:** a reproducible 0–5% (below-threshold) reduction is reported as such, never hidden. STOP and report.
- [ ] 4.5 **At every gate: STOP and report; ATE-gate judgment NOT delegated.** Report pass / below-threshold / fail + data + provenance, and hand the decision to the user. Do NOT re-design, re-tune, or swap sequences/grades unilaterally.

## 5. CARLA fidelity calibration (hard requirement — blocks the reviewer's second knife)

- [ ] 5.1 Run the CARLA point at bias=0.05°/hr and compare its VIO behaviour to the KAIST real 0.05°/hr behaviour against a defined consistency threshold (e.g. relative ATE diff < X%). **[Compliance]** If the threshold is not met, do NOT claim cross-grade conclusions. (TODO: fill X% and the calibration numbers after the run — do not invent.) **[Verification]** Confirm all CARLA grades use Allan-variance parameters so "grade" is physical. STOP and report.

## 6. Real-vehicle feasibility validation (physical FOG; proves it runs only; NOT in primary data)

- [ ] 6.1 Run the physical FOG (0.03°/hr) end-to-end to prove the pipeline runs on real hardware. **[Compliance]** This is a feasibility check only; it does NOT enter the primary dataset and is NOT a gate claim.

## 7. Documentation

- [ ] 7.1 Keep RELATED_WORK_DIFF.md and PAPER_MATERIAL.md current as tasks resolve (fill the confirmed CARLA facts, the four Pit-3 fixes, and the gated results as they land).
- [ ] 7.2 **[Flow Review]** Read proposal.md, design.md, the delta spec, and this task list end-to-end; verify the five anchors, the three innovations, the AI-in-fusion-layer lock (Anchor 2), the three pits (especially Pit 1 as spec REQUIRED), the rotation-only scope, the LOSO lock, the CARLA-fidelity gate, and the isolation rule are stated consistently with no contradictions or dangling TODOs beyond the explicitly-deferred numbers.
