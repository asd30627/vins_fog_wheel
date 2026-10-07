# REVIEWER ATTACK PLAN — Paper-2 Draft v0.1

> Anticipated reviewer attacks, our current evidence, and the rebuttal / required action. Brutally honest:
> where we have no defense yet, it says so. Sorted by severity.

## SEVERE (could sink the paper if unaddressed)

### R1. "A one-line constant-velocity gate matches/beats your model — why the complexity?"
- **Evidence they'll cite:** `cv_smoothing_gate` AURC 0.288 (KITTI in-domain), and it **beats** TCSV on direct
  transfer (CARLA→KITTI 0.327 vs 0.406; KITTI→CARLA 0.805 vs 0.823).
- **Rebuttal:** `cv_residual` IS a temporal-consistency statistic — its strength *confirms* our thesis (the signal
  is temporal-consistency, not geometry). TCSV's learned combination wins **in-domain** (KITTI 0.210 vs 0.288) and
  under **target calibration** (held-out 0.213 vs 0.236); it adds value when distributions match. We will present
  the CV gate as a first-class baseline and position TCSV as the calibrated/in-domain improvement, not a universal win.
- **Action:** keep CV gate prominent; add bootstrap CIs; soften "beats baselines" to scenario-specific claims. `[P2-4]`

### R2. "KITTI depth is monocular — your velocity labels and bbox-depth feature are confounded."
- **Status:** TRUE, no full defense yet. Monocular bbox-height depth; image_03 corrupted.
- **Action:** **stereo KITTI redo (P0-5)** before submission; rerun all KITTI numbers. State explicitly until done.

### R3. "Novelty over Qiu 2018 / observability gating is unclear."
- **Evidence we have:** qiu_style(proxy) underperforms TCSV in-domain (CARLA 0.712 vs 0.703) and geometry-only is
  weak (importance: GEO ≪ TEMP). We frame difference as learned multi-class + selective-risk + temporal signal.
- **Gap:** proxy ≠ original; no claim-boundary table yet.
- **Action:** **Qiu claim-boundary table (P0-6)**; never claim "first observability gate"; label proxy clearly.

## MODERATE

### R4. "Your SelectiveNet baseline is just your own MLP."
- **Status:** TRUE — `selectivenet_proxy` = softmax-response of an MLP ≈ TCSV-MLP (numbers nearly identical).
- **Action:** implement a real joint-trained SelectiveNet (predictor+selector+coverage loss) — needs torch `[TODO]`.
  Until then, label it honestly as a selection-mechanism proxy, not an independent architecture.

### R5. "Small in-domain CARLA margin (0.703 vs 0.712) — is this noise?"
- **Status:** legitimate; margin is within plausible noise.
- **Action:** bootstrap CIs over runs `[P2-4]`; lead with KITTI (large margin) as the headline; treat CARLA as
  corroborating, not the main claim.

### R6. "Your engineered residuals don't actually help (net neutral)."
- **Status:** TRUE and reported. CARLA 0.829→0.800, KITTI 0.919→0.923.
- **Rebuttal:** the contribution is the *selective-prediction formulation + risk-coverage evaluation +
  interpretable temporal features*, not a feature-accuracy gain. We state this plainly (no oversell).

### R7. "Planner relevance is thin (one dataset, range-rate TTC)."
- **Evidence we have:** CARLA TTC — refusal cuts overconf-accepted 0.214→0.156, false_alarm 0.200→0.140 @cov0.8.
- **Gap:** KITTI TTC missing; missed_risk not improved (velocity removed, not rescued).
- **Action:** KITTI TTC + position-only TTC fallback `[P1-1]`; frame as a minimal probe, not a planner.

## MINOR

### R8. "No confidence intervals / significance."
- **Action:** bootstrap CIs for AURC & overconf@ret `[P2-4]`.

### R9. "Calibration?" — **ALREADY DEFENDED.** raw ECE 0.02–0.03; post-hoc doesn't help. `PAPER2_CALIBRATION_RESULTS.md`.

### R10. "Leakage?" — **ALREADY DEFENDED.** provenance + shuffle ≈0.5 + no GT∩ + single-feat max 0.827. `PAPER2_LEAKAGE_AUDIT.md`.

### R11. "Grouping/eval hygiene?" — **DEFENDED.** by-run/by-seq splits, never frame-random; CARLA cross-town
grouping bug found & fixed (0.873→0.800) and disclosed. `[P0-1: scrub old report]`

### R12. "Phenomenon is a collision/threshold artifact?" — **DEFENDED.** 3.8% near-contact, trend persists;
threshold-robust 14/18 (failures only at loose τ). `PAPER2_CARLA_COLLISION_AUDIT.md`, `..._THRESHOLD_ROBUSTNESS_REGROUPED.md`.

### R13. "Only synthetic + one real dataset; generalization?" — direct transfer weak (disclosed); mixed-train
recovers. **Action:** third-dataset feasibility `[P2-2]`.

## Defense readiness scorecard
| attack | severity | defended now? |
|---|---|---|
| R1 CV gate | severe | PARTIAL (narrative + CIs needed) |
| R2 stereo | severe | NO (P0-5) |
| R3 Qiu novelty | severe | PARTIAL (P0-6) |
| R4 SelectiveNet proxy | moderate | NO (honest label only) |
| R5 small CARLA margin | moderate | PARTIAL (CIs) |
| R6 residuals neutral | moderate | YES (honest framing) |
| R7 planner thin | moderate | PARTIAL (P1-1) |
| R8 CIs | minor | NO (P2-4) |
| R9 calibration | minor | YES |
| R10 leakage | minor | YES |
| R11 eval hygiene | minor | YES (P0-1 cleanup) |
| R12 artifact | minor | YES |
| R13 generalization | minor | PARTIAL |

**Bottom line:** 3 severe attacks; 1 fully blocked only by stereo redo (R2), 2 need cheap docs/narrative (R1, R3).
Calibration, leakage, eval hygiene, phenomenon robustness are already defensible.
