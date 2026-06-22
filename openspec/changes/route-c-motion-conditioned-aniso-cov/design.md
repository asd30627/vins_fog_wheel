## Context

This change sits inside **Framework 2** of the FOG-aided VINS learned-covariance program (decision recorded in `.claude/memory/m1-fog-backbone-decision.md`; execution context in `FRAMEWORK2_PLAN.md`). Framework 2 = the learned per-feature covariance **adds on top of** the FOG backbone (it does not replace it). FOG backbone urban28 baseline ATE = **15.49**.

**Current state (facts established by read-only investigation):**

- The deployed `reliability_cov.onnx` is **geometry-only**: 10 inputs `[lp11, lp22, lp21, logZ, disp, inv_disp, radius, logtrack, nx, ny]`. It is consumed in `estimator.cpp::computeFeatureReliabilityAnisoLearned()` (~line 3577), which decodes the net output to an anisotropic information matrix and deploys it **shape-only** (`det≈1`, magnitude normalized out).
- The 10 inputs are assembled in training by `dl_reliability_ws/build_perfeat_window_dataset.py` from a KAIST **perfeat CSV** (`p1_wheel_v3_codefreeze/dl_perfeat`); `train_cov_nll.py` trains, `export_cov_onnx.py` exports. The `--vg/--fog` flags already add input dims dynamically.
- An offline diagnostic (CARLA `dynamic_dense` run01+run02; pure Python, no estimator change) showed that **after ego-flow subtraction** the per-feature object-motion residual flow is strong and directional: magnitude 4.2× (r=0.57 with `obj_speed`), within-object coherence R=0.997 (null 0.47), cross-frame stability 10.3° (static 122.5°).

**Constraint:** the geometry-only net has no motion input → it cannot orient anisotropy to the object-motion direction. The physics exists in the data; the net cannot express it. Route C closes that gap by adding a motion input.

## Goals / Non-Goals

**Goals:**
- Add a **deployable, FOG-independent** per-feature motion input (full ego residual flow) so the covariance net can learn motion-aligned anisotropy.
- Keep the training target and the shape-only deploy path unchanged; reuse the existing pipeline and `--vg`-style input-extension machinery.
- Define **hard, quantitative** acceptance gates: do-no-harm on clean, statistically-significant win on corruption.
- Preserve bit-invariance (env-gated, default-OFF) and golden-vector parity (C++ ↔ PyTorch).

**Non-Goals:**
- Changing the FOG/IMU/wheel backbone, or replacing FOG (that is Framework 1, REJECTED).
- Changing to a magnitude-downweight deploy (Route A) — the directional evidence argues against it.
- Using vg/fog cross-modal signals as the motion input (see Decision 2).
- Mechanism validation on CARLA as a training prerequisite (it is deferred; see Decision 5).
- Proving the net *learns* the alignment now — that is the pre-registered open risk, verified post-training.

## Decisions

### Decision 1 — Motion input = A+: raw optical flow + wheel-motion parts; net learns ego subtraction
**Chosen.** The motion inputs are `vx_j,vy_j` (raw optical flow) + `w_dx,w_dy,w_dtheta` (wheel SE(2) motion), on top of the existing depth (`logZ,disp,inv_disp`) and position (`nx,ny`). The net reconstructs `ego_flow = f(wheel motion, per-feature depth, position)` and subtracts it internally; it is NOT fed a precomputed residual. Input grows **10 → 15** (+5). All inputs are deployable with no new sensors (`FeaturePerFrame.velocity` `feature_manager.h:65`; `wp->dx/dy/dtheta`; depth/position already in the 10-dim set).
**Why not feed `velocity − predict()` (the earlier wording):** that precomputed residual = `velocity − wheel-reproject(i→j)` = NLL target ÷ dt → **circular** (degenerates to IRLS; memory: "inputs deliberately EXCLUDE the residual"). A+ avoids this — wheel motion parts are ego *quantities*, not the residual.
**Why A+ over bare raw velocity:** bare raw velocity forces the net to infer ego from scratch; A+ hands it the wheel-motion parts so the task becomes "assemble ego_flow from parts, then subtract" — a learnable closed-form function. Diagnostic showed raw flow alone already has 4.2× magnitude separation; the parts make the *directional* subtraction learnable.
**Key structural advantage:** every A+ input (velocity/wheel/depth/position) is a **cov-independent observable** → identical at train (cov off) and deploy (cov on) → **no train/deploy skew, no self-reference**.
**Known limitation (accepted):** wheel gives yaw only → pitch/roll ego rotation unmodeled. Small on KAIST flat roads; full angular rate would need FOG (violates Framework 2). This is the necessary cost of "don't touch FOG".
**Alternatives:** (a) bare raw velocity — superseded by A+ (kept conceptually as the floor). (b) `velocity − predict()` — rejected (circular). (c) gyro/vg residual — rejected (FOG-derived, Decision 2). (d) VINS-pose ego flow (full 6-DOF) — deferred to ablation (Risks: self-reference + skew).

### Decision 2 — Do NOT use vg/fog as the motion input (narrative separation)
FOG's role is **rotation precision** inside IMU preintegration — the moat. cov's motion signal must come from an **independent** source: visual optical flow vs ego-motion inconsistency. If the motion input mixed vg/fog, cov would be partly a re-packaging of FOG, inviting the reviewer question "is cov just FOG twice?". A+ (raw optical flow + wheel motion parts, no fog/gyro) keeps the two weapons cleanly separated and non-overlapping: **FOG = rotation precision; cov = visual-flow-vs-wheel-ego inconsistency to catch dynamic objects.** This is a deliberate, locked decision, not an empirical one.

### Decision 3 — NLL training target unchanged (wheel-reference reprojection residual)
The supervision stays `ex_norm, ey_norm` (the independent wheel-SE(2)-reference residual already produced by `build_perfeat_window_dataset.py`). Dynamic features have large, directional residuals, so the **existing** NLL-against-residual objective already teaches anisotropy **once the net has a motion input to condition on**. No new label is designed. Adding a motion input is therefore a *conditioning* change, not a supervision change.
**Alternative considered:** a new dynamic/static or object-direction label — rejected as unnecessary and as a source of leakage/circularity.

### Decision 4 — Add the input dims via the existing `--vg` mechanism; keep deploy env-gated
`train_cov_nll.py`/`export_cov_onnx.py` already extend `INPUTS` for `--vg/--fog`; the 5 A+ inputs follow the same pattern, and `cov_norm.npz` (mu/sd) auto-handles new dims. The C++ deploy appends the 5 A+ inputs (`vx_j,vy_j,w_dx,w_dy,w_dtheta`) to the `feats` vector (**10 → 15**), gated by env / default-OFF so the baseline stays **bit-invariant**; golden-vector parity (`M1_covariance_parity_spec.md`) is extended by **5 dims**. (The perfeat CSV already carries `w_dx,w_dy,w_dtheta`; PRE-TASK 1 only had to add `vx_j,vy_j` — done.)

### Decision 4b — VINS-pose ego flow is a DEFERRED ablation, not the main line
Using the VINS-solved camera pose increment to compute a full 6-DOF ego flow (then subtracting from raw flow) would capture pitch/roll that A+ misses, and is **not** target-circular (the NLL target uses the wheel reference, which is not in the factor graph; the VINS pose is a visual+IMU solve — different source). It is rejected as the main line for two reasons that match the project's known traps: **(1) self-reference / chicken-and-egg** — cov changes the factor weights → changes the VINS pose → which feeds back as the cov input (an IRLS-like loop, weak under the current shape-only deploy but present); **(2) train/deploy skew** — training perfeat uses a cov-off reference pose, deploy uses a cov-influenced pose, so the ego-flow source differs. If A+ passes the win gate but we want to approach the diagnostic's full-6-DOF ceiling, try this as an ablation and measure stability empirically first.

### Decision 5 — Task priority: measure FOG-base variance first, then KAIST perfeat, then (deferred) CARLA mechanism data
- **PRE-TASK 0 (required, runs FIRST):** before any Route C training, run FOG-base on the corruption trio (urban35-seoul / urban31-gangnam / urban36-seoul), **5 isolated reps**, and measure the median-ATE run-to-run variance (distribution / std). This **fixes the concrete corruption-win % threshold** (the one space currently left open). It depends on nothing in Route C, and the FOG-base variance is itself a required paper number — so it is the cheapest, earliest thing to run.
- **PRE-TASK 1 (required):** the Route C training source is the KAIST perfeat CSV, which currently has **no per-feature velocity column** (verified). It must be regenerated after the logger change. The `sigma_uv=0` wall does **not** recur here: `lp11/lp22/lp21` are built from the wheel covariance `w_*` columns, which are populated (verified `w_valid` 100%, `w_c00/c22` 100% finite) — that wall was specific to the old fwvio CARLA parquet. (Note: `f_*`/FOG columns are empty in the current frozen CSVs, but per Decision 2 Route C does not use fog, so a fog-mode re-run is **not** required.)
- **PRE-TASK 2 (deferred):** CARLA dynamic data regenerated via the wheel-WS perfeat logger (needs wiring `carla_stereo_player` → wheel-WS `vins_node` + a CARLA runner) is for **mechanism validation only** (does the net actually orient anisotropy to object motion — the Q2b question). It is **not** a training prerequisite and is done **only after** Route C beats the FOG baseline on KAIST.

### Decision 6 — LOSO evaluation; eval-fold vs deployment model; CARLA is a relay, not an alternative
**Chosen** because all gate sequences (win trio urban35/31/36, do-no-harm urban28/29/26/27) sit inside the 8-sequence training pool — training on all 8 then testing on them is train-on-test leakage.
- **Why LOSO and not a held-out split:** the dataset is small and the *dynamic-heavy* sequences are even fewer (35/31/36 + 39). Any split that moves dynamic sequences out of training **self-sabotages** — it weakens the dynamic→anisotropy signal the net must learn. LOSO holds out one test sequence per fold while keeping the *other* dynamic sequences in that fold's training set, so it is the only option that gets **both** zero leakage **and** retained dynamic signal. The cov net is tiny and cheap to train, so training several LOSO folds is low-cost. Held-out/fixed splits are rejected.
- **Eval-fold vs deployment model (locked):** LOSO produces several models. The ATE for any gate sequence comes ONLY from the fold that excluded it (the win number is exclusively from held-out folds). A single all-data model may be trained as the **deployment deliverable** (the real-car artifact), but it has seen every sequence, so it is labeled deployment-only and is NEVER used for a win/do-no-harm claim. This is an anti-cherry-pick lock (see the LOSO requirement in the spec).
- **CARLA is a relay, not the KAIST alternative:** CARLA-as-test (cross-dataset, naturally zero-leakage) was considered. It is NOT a substitute for LOSO — it is PRE-TASK 2 mechanism validation (does the net orient anisotropy to object motion), gated AFTER the KAIST win. LOSO settles the KAIST ATE-leakage; CARLA adds cross-dataset mechanism evidence. Both run, in relay.
**Alternatives considered:** (a) held-out trio — rejected (self-sabotages dynamic signal). (b) CARLA-as-win-test instead of KAIST — rejected as a *replacement* (kept as the PRE-TASK 2 relay).

**Approved LOSO fold table (8 folds + deployment model), clean-only, fog-mode:**

| Fold | held-out test | training set (other 7) | role |
|---|---|---|---|
| F-35 | urban35-seoul | 26,27,28,29,31,36,39 | **win** |
| F-31 | urban31-gangnam | 26,27,28,29,35,36,39 | **win** |
| F-36 | urban36-seoul | 26,27,28,29,31,35,39 | **win** |
| F-28 | urban28-pankyo | 26,27,29,31,35,36,39 | do-no-harm |
| F-29 | urban29-pankyo | 26,27,28,31,35,36,39 | do-no-harm |
| F-26 | urban26-dongtan | 27,28,29,31,35,36,39 | do-no-harm |
| F-27 | urban27-dongtan | 26,28,29,31,35,36,39 | do-no-harm |
| **F-39** | urban39-pankyo | 26,27,28,29,31,35,36 | **mid-dynamic trend datapoint** |
| deploy | — | all 8 | deployment-only (never a gate claim) |

**F-39 role (decided):** urban39 is the single *mid-dynamic* sequence (heavy 35/31/36; light 28/29/26/27; 39 in between). The win/do-no-harm gates only probe the two extremes; F-39 adds an independent datapoint at the middle. It is NOT a win or do-no-harm claim — it is evidence for whether the Route-C gain varies **monotonically with dynamic level** (a reviewer-anticipated question: "is the gain proportional to how dynamic the scene is?"). Near-zero cost (the cov net is cheap). Each win fold keeps the other two dynamic sequences in training; F-39 keeps all three heavy sequences in training.

## Risks / Trade-offs

- **[PRE-REGISTERED RISK — central] Existence of signal ≠ net captures it.** This design is justified by **physical-existence** evidence (the object-motion directional signal is real, strong, deployable). Whether the net actually **learns** to orient its anisotropy along that direction (Q2b) is **not** guaranteed now. → Mitigation: verify post-training via PRE-TASK 2 (CARLA mechanism validation: cov principal axis vs ego-residual-flow direction on dynamic features). Treat a negative result as a model/feature-engineering signal, not a silent failure.
- **[Risk] Clean-ATE net loss recurs (the C2/scalar-reliability 1.073 trap).** → Mitigation: the **do-no-harm gate** is a hard acceptance criterion — on clean sequences FOG+Route-C must show **no statistically significant ATE degradation** vs FOG-base (noise-internal fluctuation and accidental improvement are allowed; only significant worsening blocks). Multi-rep, isolated. Route C does not ship if it significantly degrades clean sequences.
- **[Risk] Train/deploy skew in the motion input.** The C++ deploy must compute the residual flow **identically** to the training-data path. → Mitigation: extend the golden-vector parity test (C++ ↔ PyTorch < 1e-5) to the new dims; single source of the residual-flow definition.
- **[Risk] CARLA short-sequence / FOG-in-sim caveats** (10–20 s clips; simulated FOG). → Mitigation: CARLA is used for **mechanism** evidence (per-frame cov-vs-motion), not ATE; ATE decisions are on KAIST. Documented in `FRAMEWORK2_PLAN.md`.
- **[Trade-off] Input grows 10 → 15 dims** and requires regenerating KAIST perfeat (re-run logging, 8 sequences). → Accepted: bounded, one-time data cost; the `--vg` precedent keeps the code change small.

## Migration Plan

0. PRE-TASK 0: run FOG-base on the corruption trio (5 isolated reps), measure median-ATE run-to-run variance, and **fix the concrete corruption-win % threshold** into the win gate. (Depends on nothing in Route C; do this first.)
1. Land the logger + pipeline + deploy changes **env-gated / default-OFF** — baseline must remain bit-invariant (verify md5/vio-rows unchanged with the flag off).
2. PRE-TASK 1: regenerate KAIST perfeat with velocity; retrain + export ONNX; pass golden-vector parity.
3. Evaluate FOG-base vs FOG+Route-C on clean (do-no-harm gate) and dynamic-heavy corruption (win gate, threshold fixed in step 0), multi-rep isolated.
4. Only if the KAIST win gate passes: PRE-TASK 2 (CARLA mechanism validation).
5. Rollback = flip the env flag OFF (returns to the geometry-only / current behavior); no data migration needed.

## Open Questions

- **Resolved — motion input is A+ (Decision 1):** raw flow `vx_j,vy_j` + wheel parts `w_dx,w_dy,w_dtheta` (10→15); the net learns ego subtraction. The earlier "residual-flow 2D / defer raw velocity" framing is superseded (it was circular). VINS-pose full-6-DOF is the Decision 4b deferred ablation.
- **Resolved — win magnitude bar:** the concrete % is fixed by **PRE-TASK 0** from the measured FOG-base run-to-run variance on the corruption trio; not left to evaluation-time guesswork.
- **Resolved (Decision 6) — CARLA's role:** KAIST dynamic-heavy trio is the win set (evaluated via LOSO); CARLA is the PRE-TASK 2 mechanism-validation relay (cross-dataset, after the KAIST win), not part of the win set and not a substitute for LOSO.

- **OPEN — why does wheel reference-only change the VIO?** Enabling the wheel topic (reference-only, no factor) perturbs the VIO trajectory (urban28: 63% of poses bit-identical, then a gradual divergence from ~64% of the sequence, max 43 m). Confirmed: reference-only writes NO solver state (code-audited) and `WHEEL=0` (wheel factor not in the graph). The exact mechanism is NOT located. Candidates: (i) heap relative-configuration perturbation touching an address/order-sensitive computation elsewhere (e.g. ceres ordering tie-break); (ii) ROS-callback interleaving (single-thread executor handling an extra `/wheel/delta` topic changes sensor-buffer ordering). The ASLR test is NEGATIVE (PRE-TASK 0: 5 reps bit-identical under full ASLR → VIO insensitive to absolute-address layout), which WEAKENS the heap hypothesis; it is not claimed as the answer. **This mechanism does NOT affect the baseline-fairness argument** (Decision 7), so it is left an open question rather than blocking the project.

### Decision 7 — wheel-on baseline (cancellation argument), with a one-time cancellation-cleanliness check
**Chosen.** FOG+Route-C must run wheel-on (cov reads `w_*`). Since wheel-on perturbs the VIO (mechanism open), the fair baseline is FOG-base **also wheel-on (reference-only, cov-OFF)**, so the wheel perturbation appears identically on both sides and cancels under subtraction — leaving cov as the only difference. This cancellation is **mathematically independent of the mechanism** and is backed by positive code evidence (reference-only writes no solver state; `WHEEL=0`).
**Precondition that MUST be verified (cancellation cleanliness):** the cancellation assumes the wheel perturbation is the *same thing, same size* with cov-off and cov-on. Because the mechanism is unknown, we cannot assume it does not interact with cov. → **One-time check on the first sequence**: when its wheel-on cov-OFF baseline and wheel-on cov-ON (Route C) are both available, the cov-induced difference must be a *plausible cov-effect magnitude*. If cov-on shows anomalous behaviour co-located/co-scaled with the 43 m wheel perturbation (a sequence suddenly diverging, or a difference far larger than a clean cov effect), the cancellation is NOT clean → STOP and report. Also watch per-sequence wheel-on-vs-off divergence magnitude: any sequence far exceeding urban28's 43 m, or affecting convergence, → STOP and report.

## Gate-Failure Diagnostics (Playbook)

Plan every branch, not only the success path. At each gate, on failure, **classify the failure and follow the indicated next step — do NOT re-design unilaterally; report and let the user decide** (see Operating Model).

### G1 — Do-no-harm gate fails (significant clean degradation; the C2/1.073 trap)
- **Check 1 — deploy integrity:** did magnitude leak into deploy? Confirm the applied per-feature matrix is still **shape-only** (det≈1 of `U`). If det deviates from 1, a bug reintroduced magnitude down-weighting → fix the deploy decode, not the model.
- **Check 2 — scope of degradation:** is the loss across **all** clean sequences, or only one/two sensitive ones? (C2 hurt only *some* sequences.)
  - *Single sensitive sequence* → inspect that sequence's dynamic/geometry character (is it actually clean? low-texture? aggressive motion exciting the residual-flow input?).
  - *All clean degrade* → the motion-input conditioning is mis-shaping covariance even on clean, where residual flow ≈ ego-fit noise. Go back to **training**: check the net isn't over-reacting to small clean residual flow; consider input scaling / a clean-flow deadband / stronger regularization.

### G2 — Win gate fails but do-no-harm passes — MUST distinguish two OPPOSITE failures
The discriminator is the **cov principal-axis alignment with object motion** (Q2b / PRE-TASK 2):
- **(a) Net did NOT learn (Q2b negative):** cov major axis does **not** align with the ego-residual-flow direction on dynamic features. → Problem is the **feature representation / network**. Next: run PRE-TASK 2 CARLA mechanism validation to confirm non-alignment, then change the input representation or net — **NOT** the test set.
- **(b) Net learned but KAIST too mild:** cov axis **does** align, but ATE doesn't move (KAIST's heaviest dynamic is only ~2.4% outlier). → Problem is the **test arena being too clean, not the method**. Next: prove on CARLA strong-dynamic; do **NOT** change the method.
- **KEY:** these two next steps are **opposite** (change method vs change arena). You MUST first check cov-axis alignment to tell (a) from (b) before choosing. Never assume which one it is.

### G3 — NLL improves but ATE does not (task 4.4 good, but 6.1/6.2 lose) — the C2 "good intermediate, lost final" pattern
- NLL = residual-prediction calibration; it is **not** ATE. A better-calibrated cov can leave the trajectory unchanged.
- **Check 1 — solver leverage:** does the cov actually change the optimizer solution? With shape-only deploy the per-feature effect may be too small to move the estimate. Inspect the optimization delta (cov on vs off).
- **Check 2 — dynamic-fraction leverage:** dynamic features are only ~1.7% of features → even correct reshaping of them has little leverage on whole-trajectory ATE. This points back to **G2(b)**: the method may be right but the regime gives it no leverage; confirm via CARLA strong-dynamic.

## Operating Model (gated execution)

This change is **gated, not a continuous run**. Three checkpoints stop for a human decision: **PRE-TASK 0** (fix the win threshold), **6.1** (do-no-harm), **6.2** (win). It is unlikely to produce a complete victory from one multi-day run; the expected mode is *reach a gate, bring data back, decide together*.

- At each gate, **STOP and report honestly**: pass/fail + the data (per-seq median ATE, variance, paired-test result, effect size) + provenance (binary md5, commit, data batch) + **which playbook branch the result hits**.
- **Do NOT push through a gate** unilaterally. **Do NOT tune** the PRE-TASK 0 threshold or **swap the sequence list** to make a result look better. Report pass **and** fail outcomes faithfully.
- On failure, **map the result to the Gate-Failure Playbook**, state which failure mode it is and the playbook's recommended next step, and **hand the decision to the user — do not re-design unilaterally**.

> **[NOTE — deferred, apply when reaching task 6.1]** PRE-TASK 0 measured FOG-base as **deterministic** (5-rep std ≤0.1%); FOG+Route-C is likely deterministic too. The win gate and eval-rigor requirement were already updated to reproducible-Δ / effect-size language (no p-values). The **do-no-harm gate (6.1)** still says "no statistically significant degradation" — this should be changed to reproducible-Δ language (e.g. "clean ATE must not reproducibly rise by more than ~1–2%") **when we reach 6.1**, not now. Left intentionally unchanged for now per user instruction.
