# Route C — Execution Status (handoff, 2026-06-22)

Full spec: `openspec/changes/route-c-motion-conditioned-aniso-cov/` (proposal/design/specs/tasks, `openspec validate` = 4/4).
Branch `p1-reliability-v1`. Binary md5 **ab166defd845** = logger commit **dd8d1e0** (estimator.cpp clean restore point before site d).

## What Route C is
Framework 2 (FOG backbone + learned per-feature anisotropic cov ON TOP, never replace). Add a **motion input (A+)** so the cov net can express motion-aligned anisotropy on dynamic features. Payoff = corruption-regime ATE; clean = do-no-harm.

## A+ motion input (FINAL, Decision 1/2/4)
Net inputs **15-dim** = geom10 `[lp11,lp22,lp21,logZ,disp,inv_disp,radius,logtrack,nx,ny]` + **5 A+** `[vx_j,vy_j,w_dx,w_dy,w_dtheta]` (raw optical flow + wheel SE(2) motion). Net LEARNS ego subtraction internally — NOT fed `velocity−predict()` (= NLL-target/dt = circular). All cov-independent observables ⇒ no train/deploy skew. Limitation: wheel yaw only (pitch/roll ego unmodeled; full angular would need FOG = violates F2). VINS-pose 6-DOF = deferred ablation (self-ref+skew, Decision 4b). NLL target UNCHANGED (ex_norm,ey_norm); cov deploy is SHAPE-ONLY (det~1).

## Progress / where we are
- **PRE-TASK 0 DONE** (FOG-base variance) — but baseline was wheel-OFF (urban35/31/36 = 60.74/108.35/260.77 m) → **VOIDED for gating** (Decision 7); must re-run wheel-ON (task 1.4). FOG-base is DETERMINISTIC (5-rep std ≤0.1%).
- **PRE-TASK 1 DONE**: 8 KAIST perfeat regenerated wheel-ON at `/mnt/sata4t/ivlab3_data/fwvio/results/route_c/pretask1_perfeat/<seq>/perfeat_<seq>.csv` — all w_valid=100% +vx_j,vy_j (envs: REL_PERFEAT_LOG=1 + REL_WHEEL_REFERENCE_ONLY=1 + **PUBLISH_WHEEL_TOPIC=1**; the last was missing first time → w_*=0, fixed). Old no-wheel kept at `…/pretask1_perfeat_nowheel_VOID/`.
- **Dataset built**: `/home/ivlab3/dl_reliability_ws/dataset/perfeat_window_aplus_wheelon.parquet` (1.4M rows, 8 seq, seq column for LOSO).
- **site b/c DONE** (in `/home/ivlab3/dl_reliability_ws`, NOT in fwvio git repo): `build_perfeat_window_dataset.py` (+vx_j,vy_j in BASE_COLS, emits 5 A+), `train_cov_nll.py`+`export_cov_onnx.py` (INPUTS +5 A+; `RC_APLUS=0`/`--geom-only` → 10-dim geometry baseline). Helpers: `build_aplus_dataset.py`, `train_fold_aplus.py`, `train_all_folds.py`. **Run with `gf` conda env** (`/home/ivlab3/miniconda3/envs/gf/bin/python`, torch cu128, RTX5090).
- **FRAME-I SKEW FIX (2026-06-22, done):** builder `build_perfeat_window_dataset.py` had `nx/ny/radius` on frame **j** while its own `lp/logZ/disp` and the deploy estimator.cpp were on frame **i** (self-inconsistent + train/deploy skew, urban28 |nx_j−nx_i| median 0.0031 ≈0.8% nx std). Changed builder `nx/ny/radius` → frame i (matches lp/disp AND deploy). A+ `vx_j/vy_j` stay frame j (raw flow), w_* unchanged. Dataset rebuilt (`perfeat_window_aplus_wheelon.parquet`, 1.4M rows; old frame-j kept `…_framej_VOID.parquet`). **CONTROL: old frame-j vs new frame-i through identical eval ⇒ NLL essentially unchanged (per-fold Δmed ~0.005–0.015)** — the fix is clean, changes no conclusion either way.
- **8 LOSO folds re-trained. NLL DISCRIMINATOR = MEDIAN (robust; consistent with median-ATE gates). CORRECTION:** earlier "median 8/8 / median=−7.128 benign" in this doc was WRONG. **By median, A+ beats geom-only 6/8, NOT 8/8.** The two LOSSES are the most-dynamic "win"-role folds: **urban35-seoul Δmed +0.068, urban36-seoul Δmed +0.203 (A+ slightly worse).** The "8/8" only holds under **mean** NLL (what spec Decision 8 originally wrote, pre-dating the urban36 outlier finding), and urban36's mean "win" is an artifact (A+ 171 vs geom 565 — both blown up by 0.11% outliers, not robust). Median is the correct discriminator; we do NOT use mean to paper over the result. dnh+urban31+urban39 still A+-win by median (Δmed −0.42~−0.98). **WARNING (not a death sentence):** NLL early-green-light did NOT light on the two key win folds (35/36). NLL is only an early reference (C2 lesson: good NLL ≠ ATE); decisive = ATE. **Proceed to ATE carrying this warning** — watch whether A+ actually delivers ATE on urban35/36.

## KEY RESULTS (evidence so far)
- **Watershed (urban28, both cov-OFF)**: wheel-OFF ATE-vs-GT 24.89 m vs **wheel-ON 18.82 m (−24%, BETTER)**; the 43 m divergence segment is CLOSER to GT wheel-on (32.78→20.28). So wheel-on baseline is fair AND a stronger baseline. (Mechanism of "ref-only changes VIO" = OPEN; ASLR-negative + systematic-improvement weaken the heap hypothesis; candidate = ROS-callback interleaving.)
- **4.4b direction-align check = VOIDED/TRIVIAL** (Decision 8): A+ aligned 11.5° BUT geom-only control also 10.2° (residual dir is hand-prior-contaminated by wheel-motion Jacobian). No discriminative power. Clean motion-direction mechanism validation → **CARLA PRE-TASK 2** (KAIST has no object-motion GT).

## IRON RULES (anti-cherry-pick — DO NOT relax)
- **win = ≥5% median ATE reduction on corruption trio AND all-3 sequences reduce (consistent direction)**; NOT 10%. A reproducible 0–5% reduction is reported honestly as "below threshold", never hidden.
- **Gate ATE numbers come ONLY from the LOSO held-out fold** (F-35→urban35, F-31→urban31, F-36→urban36, F-28/29/26/27→do-no-harm). The all-data **deployment model NEVER provides a gate number**.
- **F-39 = mid-dynamic trend datapoint**, NOT a win/do-no-harm claim.
- **do-no-harm**: clean (urban28/29/26/27) must show NO statistically/ reproducibly significant ATE degradation vs FOG-base.
- FOG-base deterministic ⇒ report reproducible per-seq Δ + % + effect size, NOT p-values.
- Decisive evidence = ATE win gate. Held-out NLL is only an early reference (C2 lesson: good NLL ≠ ATE). **NLL discriminator = MEDIAN** (robust, consistent with the median-ATE gates); mean is NOT used to override median when they disagree (urban36 mean is outlier-blown). This is an early-green-light discriminator correction, NOT a change to the win gate's locked ≥5% median-ATE bar (that stays fixed).
- **NLL EARLY-GREEN-LIGHT DID NOT LIGHT ON urban35/36** (the two key win folds): A+ lost by median there. This is a WARNING carried into ATE, not a stop. Watch urban35/36 ATE especially.

## NEXT = site d (C++ deploy) — then ATE
1. **STOP-AND-REPORT: commit restore point** before touching estimator.cpp (clean at dd8d1e0). [user gate]
2. **site d**: `estimator.cpp::computeFeatureReliabilityAnisoLearned` (~line 3577). Append 5 A+ inputs to the `feats` vector (10→15): `vx_j=fj.velocity.x()`, `vy_j=fj.velocity.y()`, `w_dx=wp->dx`, `w_dy=wp->dy`, `w_dtheta=wp->dtheta` (wp already in scope). Keep env-gated/default-OFF. Extend golden-vector parity +5 dims.
3. `colcon build --packages-select vins`; export per-fold ONNX (RC_APLUS=1) + deployment ONNX (labeled deployment-only).
4. **bit-invariance — TWO SEPARATE checks (do NOT conflate, site d ≠ logger):**
   - (1) **cov-OFF path** (env default OFF) MUST stay bit-identical to dd8d1e0 — proves no breakage of existing behaviour. Not identical → STOP-and-report.
   - (2) **cov-ON** must be *active and sane* — it SHOULD change the VIO (else cov does nothing); verify it is not divergent/garbage, not bit-identical.
5. **task 6.0 cancellation-cleanliness check** (when cov-ON exists, first sequence): cov-on-vs-cov-off difference is a plausible cov magnitude, not co-scaled with the 43 m wheel perturbation. Anomalous → STOP.
6. Deploy each fold's ONNX → run **held-out ATE wheel-on** (FOG-base wheel-on cov-OFF vs FOG+Route-C wheel-on cov-ON), multi-rep isolated, per the harness (`scripts/run_one_p1_baseline.sh` direct, wheel-on via PUBLISH_WHEEL_TOPIC; NOT the unsafe `run_p1_one.sh`).

## ⛔ ATE GATE JUDGMENT IS NOT DELEGATED
You MAY autonomously produce ATE numbers. You MUST NOT judge 6.1/6.2 pass/fail or declare "won/met". When ATE numbers exist, **STOP** and lay them out as a raw table (per-seq, per-rep, baseline wheel-on cov-OFF vs cov-ON, held-out fold only) and WAIT for the human to judge the gate. A new session inheriting this must see "raw numbers + UNJUDGED", never a pre-declared win. (History: the INVALID 33.73 "win" was a self-declared success not caught in time.)

## ✅ ROOT CAUSE of the "632 m blowup" = FIXEDEXT HARNESS BUG (CORRECTED 2026-06-23) — NOT nondeterminism, NOT site d
**CORRECTION of an earlier misjudgment in this doc.** During site-d bit-invariance(1) the cov-OFF path appeared to diverge wildly (urban28 ATE 18.82 vs 632 m) and was WRONGLY hypothesized to be "wheel-on run-to-run nondeterminism." **That conclusion was WRONG. Real root cause: my bit-inv/orchestrator scripts called `run_one_p1_baseline.sh` DIRECTLY without exporting `USE_EXPLICIT_FIXEDEXT=1`, so the harness silently fell back to the legacy base-template extrinsic (`kaist_stereo_xsens.yaml`, body_T_cam0 tx=1.71239) instead of the per-seq calibrated fixedext (`kaist_urban28-pankyo_fixedext.yaml`, tx=1.45166).** Wrong stereo extrinsic → wrong depth → VIO diverged to 632 m. The dd8d1e0 baseline (18.82 m) was run via regen.sh which DOES export `USE_EXPLICIT_FIXEDEXT=1`. So baseline-vs-mine was apples-to-oranges (different extrinsics). **New binary, estimator, and site d are all CLEAN** (the determinism I saw — new1≡run1 632 m bit-identical across pb 3.0/1.0 — was the new binary being *deterministic with the wrong extrinsic*).
- **FIX (committed):** `run_one_p1_baseline.sh` default `USE_EXPLICIT_FIXEDEXT` changed **0→1** (always fixedext); the legacy base-template path now **ERROR-STOPS** unless an explicit `ALLOW_LEGACY_BASE_EXTRINSIC=1` ack is set (loud warning). Net: every run uses the correct per-seq fixedext OR stops — never silently the wrong extrinsic. All 8 Route-C seqs have fixedext configs; all sequence-running scripts now covered. Verified all 4 branches (default→fixedext, =0→error, =0+ack→warn, =1+missing→error).
- **Minor real sub-finding (kept):** at playback_rate **3.0** under load, VINS can fall behind real-time and TRUNCATE output (new2 stopped at 916 s / 9166 rows). So the isolation protocol below is still good practice, but it was NOT the cause of the 632 m — the extrinsic was.
- **Watershed (18.82 wheel-on vs 24.89 wheel-off):** the extrinsic bug does NOT invalidate it (both arms were fixedext). Its single-run / pb-3.0 robustness is separately still unverified (re-confirm with the clean protocol when convenient), but it is NOT "inside an 18–632 m spread" — that spread was the extrinsic artifact.
- **wheel-on clean-env determinism (task 1.4) is STILL genuinely open** — my determinism runs were all on the WRONG extrinsic, so they don't answer it. Re-run with fixedext (now the default) to measure it.
- **Isolation protocol (still recommended for ATE):** playback_rate **1.0**, one VINS at a time (no concurrent build/python), completion precondition = full ~19735 rows / ~1973 s (truncated run = invalid).
- **STATUS:** root cause fixed. The REAL bit-invariance(1) is now redoable: new binary cov-OFF **WITH fixedext (default)** vs the 18.82 m baseline (apples-to-apples). ⛔ Still do NOT touch ONNX / parity / cov-ON / task 6.0 / ATE until the user oks the verification re-run.

## Still UNVERIFIED / OPEN
- **wheel-on clean-environment determinism (task 1.4) — STILL OPEN** (my earlier runs used the wrong extrinsic; redo with fixedext default). Gates ATE.
- task 6.0 cancellation cleanliness (needs cov-on).
- Mechanism of wheel-ref-only changing+improving VIO (OPEN; not heap per ASLR-negative + systematic improvement).
- CARLA PRE-TASK 2 mechanism validation (cov axis vs GT object motion) — gated AFTER KAIST win; data at `/mnt/sata4t/datasets/carla_fwvio/Town10HD__dynamic_dense__run01/02` (has fog_synth, wheel_synth, per-frame GT JSON w/ per_instance velocity, seg). Needs CARLA player wired to wheel-WS + per-frame REL_COV_DUMP patch.

## Commits (fwvio repo)
29e5815 spec lock+wrapper · ebb19cd M0/M1 base · b29c625 spec git-track · **dd8d1e0 logger +vx_j,vy_j (restore point)** · 57da8ae LOSO spec · 75c2ab4 wrapper PUBLISH_WHEEL_TOPIC · 231978e spec A+/Decision7/open-mech. (site b/c live in dl_reliability_ws, not this repo.)
