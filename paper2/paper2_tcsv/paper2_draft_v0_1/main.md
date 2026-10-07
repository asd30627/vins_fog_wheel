# Temporal-Consistency-Aware Selective Object State Validity for GPS-Denied Navigation

> **Journal Draft v0.1 — NOT submission-ready.** Updated from `paper2_draft_v0/main.md` with the full baseline
> suite (Part C), leakage audit, regrouped threshold robustness, calibration, and a planner-facing TTC probe
> (Part D). Open items remain inline as `[TODO: ...]` (tracked in `PAPER2_FULL_MISSING_EXPERIMENTS_PLAN.md`,
> `EXPERIMENT_GAP_AUDIT.md`). All numbers are post CARLA `(town,run,track_id)` grouping fix.
> **Honesty flag:** a one-line constant-velocity gate (`cv_smoothing_gate`) is a strong baseline and even beats
> TCSV on direct cross-dataset transfer — reported plainly in §VII.

---

## Abstract (draft)

GPS-denied navigation increasingly relies on estimating the state (position, velocity) of *other* dynamic objects
from on-board vision/VIO. On synthetic (CARLA) and real (KITTI) driving we show object *velocity* is frequently
invalid even when *position* is usable: velocity validity collapses with range while position degrades gracefully,
creating a substantial **position-only regime**. We recast object-state estimation as **selective prediction**:
a layer that decides *when to trust* a velocity estimate and otherwise refuses to position-only. We formalize
**TCSV (Temporal-Consistency Selective Validator)**, scoring per-estimate validity from runtime-observable features
centered on the **temporal self-consistency of the raw estimate**, and we evaluate with **selective-risk /
risk-coverage** metrics (overconfident-wrong-velocity at a chosen coverage) rather than accuracy alone. Against a
full baseline suite (distance gate, a Qiu-style observability-gate proxy, detector-confidence and bbox-depth gates,
a constant-velocity smoothing gate, a SelectiveNet-style selector proxy, and an observability index), TCSV achieves
the best in-domain selective risk (AURC 0.210 KITTI, 0.703 CARLA) and the best mixed-train→held-out transfer, while
we report honestly that (i) a single constant-velocity-residual gate is a strong baseline that **wins on direct
cross-dataset transfer**, (ii) hand-designed residuals do not net-improve over a simpler temporal feature set, and
(iii) the dominant signal is the raw-speed-based temporal-consistency, not any one engineered residual. A
planner-facing TTC probe shows refusal cuts overconfident velocities accepted by a downstream collision check from
0.21 to 0.16 at 80% coverage. We do **not** modify the VIO back-end, add object factors, or claim improved
ego-localization. `[TODO: refresh abstract numbers after stereo-KITTI redo and SelectiveNet full impl]`

---

## I. Introduction
*(unchanged in substance from v0 — motivation, position-only regime, temporal-consistency lever)*

**Contributions.**
- **C1.** Cross-dataset (CARLA + real KITTI) characterization of dynamic-object **velocity-validity**: collapses
  with range, position more stable, position-only regime real, robust to detection thresholds and to
  near-contact/collision filtering.
- **C2.** **TCSV**, a selective validator formalizing object-state validity as *selective prediction* over
  runtime-observable temporal-consistency features, evaluated and compared on **selective-risk** metrics against a
  full baseline suite. We are explicit (§VII-B) that the contribution is the *formulation + evaluation*, not a
  feature trick, and that a simple CV-residual gate is a strong honest baseline.
- **C3.** A **refusal-aware, planner-facing evaluation** (risk-coverage, overconfident-velocity accepted by a TTC
  check) quantifying validity at the decision level.

**Explicit non-claims.** No VIO back-end change; no object factors; no frontier/trajectory planning method
(→ Paper-3); no improved ego-localization; not the first observability gate.

---

## II. Related Work
A. Dynamic-object SLAM/VIO (VDO-SLAM, DynaSLAM II, ClusterVO) — estimation, not refusal.
B. Object/detection uncertainty — confidence, bbox/depth uncertainty (our gates #4–5).
C. Selective prediction / reject option — SelectiveNet, learning-to-defer, risk-coverage (our framing + metrics).
D. Planner-facing reliable / introspective perception.
E. **Boundary vs Qiu 2018:** geometric observability threshold (binary) vs our learned multi-class selective
   validator driven by temporal-consistency, with decision-level metrics on real data. **We do not claim first
   observability gating.** `[TODO: Qiu 2018 claim-boundary table — P0-6]` `[TODO: full reference cells T1]`

---

## III. Problem Formulation
Label (GT used for evaluation only): $y_t=\mathbb 1[\lVert\hat v_t-v_t^{gt}\rVert\le\tau_v]$, $\tau_v=3$ m/s.
Selective validator learns $g_\theta(x_t)\in[0,1]$, emit threshold $\rho$; emit velocity if $g_\theta\ge\rho$ else
refuse to position-only. Objective = selective-risk / risk-coverage trade-off (minimize overconfident-wrong velocity
at target valid-retention), not classification accuracy. $x_t$ uses no GT and no back-end internals.
`[TODO: formal AURC / risk-coverage definition block]`

---

## IV. Method: TCSV

### A. Temporal self-consistency features (14, runtime-observable)
GEO(5): range, bearing, bbox_area, depth, det_conf. TEMP-base(2): track_age, raw_speed.
TEMP-residual(7): cv_residual, acceleration_score, jerk_score, velocity_direction_flip_count,
bbox_depth_consistency, short_window_position_jitter, short_window_velocity_jitter. Window $W{=}5$.
**Leakage audit (§VII-D / `PAPER2_LEAKAGE_AUDIT.md`):** no feature ∩ GT columns; max single-feature AUROC 0.827;
shuffled-label AUROC ≈0.5 ⇒ no structural leak.

### B. Model family (deliberately minimal)
TCSV-rule (depth-3 tree), TCSV-HistGBM (main), TCSV-MLP (64,32). No transformer/attention/large nets.

### C. Selective-risk objective & operating evaluation
Risk-coverage curve, AURC↓, overconfident-velocity@retention 0.8/0.9, plus AUROC/overconf/retention/false_refusal/
F1_invalid. `[TODO: training-time selective objective; current = standard loss + threshold]`

---

## V. Dataset and Validity Benchmark
CARLA dynamic_v3 ($n{=}15{,}811$, dt 0.05, base vel-valid 0.112); KITTI tracking (21 seqs, YOLOv8m + **monocular**
bbox-height depth, $n{=}37{,}022$, dt 0.1, base vel-valid 0.430). `[TODO: stereo KITTI redo — P0-5]`

### A. Velocity-validity phenomenon (C1) — validity by range bin
| bin | CARLA pos | KITTI pos | CARLA vel | KITTI vel |
|---|---|---|---|---|
| 0–15 m | 0.89 | 0.86 | 0.70 | 0.65 |
| 15–30 m | 0.73 | 0.74 | 0.26 | 0.45 |
| 30 m+ | 0.30 | 0.44 | 0.08 | 0.21 |
All four sub-phenomena reproduce on real KITTI.

### B. Robustness
- **Threshold-robust (regrouped):** C1 checks pass 14/18 pos×vel combos; the 4 failures are only at the loose
  $\tau_v{=}5$ m/s setting where near-range velocity is mostly valid by construction (expected, not a defect).
  TCSV beats the distance gate (AURC↓) in 6/6 $\tau_v$ settings (`PAPER2_THRESHOLD_ROBUSTNESS_REGROUPED.md`).
- **Not a collision artifact:** 24-run near-contact audit → 3.8% near-contact frames (3 contaminated runs);
  excluding them leaves the trend unchanged (dense car-following, not collisions).

---

## VI. — (folded into V/VII)

---

## VII. Experiments
Splits: CARLA by run, KITTI by sequence, + CARLA→KITTI, KITTI→CARLA, CARLA+KITtrain→held-out-KITTI,
KITtrain+CARtrain→held-out-CARLA. Never frame-random. Full table: `PAPER2_PUBLIC_PROXY_BASELINE_RESULTS.md`.

### A. Selective-risk: TCSV vs full baseline suite (AURC↓, headline)
| split | best NON-ours baseline | TCSV-HistGBM | verdict |
|---|---|---|---|
| CARLA→CARLA (run) | qiu-proxy 0.712 | **0.703** | BEATS (margin small) |
| KITTI→KITTI (seq) | cv_smoothing 0.288 | **0.210** | BEATS |
| CARLA+KITtrain→held-out-KITTI | selnet-proxy 0.236 | **0.213** | BEATS |
| KITtrain+CARtrain→held-out-CARLA | qiu-proxy 0.718 | **0.685** | BEATS |
| CARLA→KITTI (direct) | **cv_smoothing 0.327** | 0.406 | **LOSES** |
| KITTI→CARLA (direct) | **qiu-proxy 0.805** | 0.823 | **LOSES** (all models poor; base-invalid 0.89) |

**Honest reading:** TCSV wins in-domain and with mixed-train target calibration, but a **one-line constant-velocity
residual gate beats it on direct cross-dataset transfer**. This *reinforces* the core thesis — `cv_residual` is a
pure temporal-consistency statistic, so its strong transfer shows temporal-consistency (not geometry) is the
generalizing signal; TCSV's learned combination adds value only when train/test distributions match or are
calibrated. `[TODO: discuss as a feature, not a bug, in final text]`

### B. New residuals vs prior OLD10 (HONEST — net neutral)
CARLA 0.829→0.800 (slightly down); KITTI 0.919→0.923 (slightly up). The engineered residuals do not net-improve
accuracy; the contribution is the formulation/evaluation. **Do not oversell.**

### C. Feature importance (permutation, ΔAUROC)
CARLA: TEMP-base 0.247 ≫ GEO 0.044 ≈ TEMP-resid 0.032. KITTI: TEMP-base 0.157 > TEMP-resid 0.093 > GEO 0.060.
Dominant feature: **raw_speed**; strongest new residual: KITTI `cv_residual` (rank 2). `[TODO: SHAP plot — P1-3]`

### D. Leakage audit
`PAPER2_LEAKAGE_AUDIT.md`: 14-feature provenance all runtime-observable/GT-free; no feature ∩ GT columns;
max single-feature AUROC 0.827; shuffled-label AUROC ≈0.5; GT-feature ceiling shown separately (never used).

### E. Calibration
`PAPER2_CALIBRATION_RESULTS.md`: raw TCSV-HistGBM ECE 0.031 (CARLA) / 0.020 (KITTI) — **already well-calibrated**;
post-hoc Platt/isotonic on a by-group calibration split does **not** improve ECE (group shift). Use raw scores for
thresholding. `figs/fig_tcsv_reliability.png`.

### F. Temporal-window ablation
$W{=}1$≈$W{=}7$; window beyond one frame adds little; $W{=}5$ mild default, not a contribution.

### G. CARLA grouping fix (honest correction)
`(run,track_id)`→`(town,run,track_id)`; CARLA in-domain AUROC 0.873→0.800 (still beats distance 0.755). KITTI
unaffected. `[TODO: propagate to PAPER2_SELECTIVE_VALIDITY_RESULTS.md — P0-1]`

---

## VIII. Planner-facing Minimal Evaluation
`PAPER2_PLANNER_TTC_RESULTS.md` (CARLA front objects, $n{=}4043$; TTC=range/closing-rate, risk if TTC<3 s):
| policy | coverage | false_alarm | missed_risk | overconf_vel_accepted |
|---|---|---|---|---|
| always-emit | 1.00 | 0.200 | 0.024 | 0.214 |
| TCSV @cov 0.8 | 0.80 | 0.140 | 0.028 | 0.156 |

Refusal cuts overconfident invalid velocities accepted by the TTC check (0.214→0.156, −27%) and false alarms
(0.200→0.140) at modest coverage cost; missed_risk barely changes. **Supports C3 (modestly).**
`[TODO: KITTI TTC (needs GT range); position-only TTC fallback variant — P1-1]`
**Scope guard:** downstream *validation* only; full planning → Paper-3.

---

## IX. Limitations (honest)
1. Direct cross-dataset transfer is weak and is **beaten by a CV-residual gate** (§VII-A).
2. KITTI uses monocular depth; stereo redo pending `[TODO]`.
3. Velocity GT differenced from GT positions (noisy).
4. Hand-designed residuals add little net accuracy (value = formulation/evaluation).
5. SelectiveNet baseline is a softmax-response proxy ≈ TCSV-MLP; a full joint-trained SelectiveNet is `[TODO]`.
6. Operating point via train-Youden, not a training-time selective objective `[TODO]`.
7. CARLA lateral-crossing regime is sparse (n=9) — under-powered for that regime.

---

## X. Conclusion (draft)
We reframed dynamic-object state estimation under GPS denial as **selective prediction** — decide when to trust a
velocity, else fall back to position-only. The velocity-validity phenomenon is real and cross-dataset; TCSV beats a
full baseline suite on selective risk in-domain and under target calibration, with the signal carried by the
**temporal-consistency of the raw estimate**. We are explicit about what does not work (engineered residuals,
direct transfer where a CV gate wins, temporal windows) and what we do not claim. The result is a planner-facing
reliability layer. `[TODO: finalize after stereo redo + Qiu table + SelectiveNet full impl]`

---

### Inline TODO index → see `EXPERIMENT_GAP_AUDIT.md` and `PAPER2_FULL_MISSING_EXPERIMENTS_PLAN.md`.
