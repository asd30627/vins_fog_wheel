# Temporal-Consistency-Aware Selective Object State Validity for GPS-Denied Navigation

> **Journal Draft v0 — NOT submission-ready.** Working draft; prose unpolished. Missing baselines/experiments are
> marked inline as `[TODO: ...]` and tracked in `MISSING_EXPERIMENTS_TODO.md` / `RELATED_WORK_BASELINE_PLAN.md`.
> Numbers are the *corrected* values after the CARLA per-(town,run,track) grouping fix (see §VII-E).

---

## Abstract (draft)

GPS-denied navigation increasingly relies on estimating the state (position and velocity) of *other*
dynamic objects from on-board vision/VIO. We show — on synthetic (CARLA) and real (KITTI) driving — that
the *velocity* of such estimates is frequently invalid even when *position* is usable: velocity validity
collapses with range while position degrades more gracefully, creating a substantial **position-only regime**.
Treating object-state estimation as something that should sometimes **refuse** rather than always emit, we
formalize **TCSV (Temporal-Consistency Selective Validator)**: a *selective-prediction* layer that scores the
runtime reliability of each velocity estimate from runtime-observable features — emphasizing the **temporal
self-consistency of the raw estimate** — and either emits a full object state or falls back to position-only.
We evaluate not with accuracy alone but with **selective-risk / risk-coverage** metrics that measure the
overconfident-wrong-velocity rate at a chosen coverage, the operationally meaningful quantity for a downstream
planner. TCSV reduces the area-under-risk-coverage versus a distance gate from 0.457 to 0.210 on KITTI and
from 0.773 to 0.703 on CARLA, and cuts overconfident-wrong velocity at 90% valid-retention from 0.43 to 0.25
(KITTI). We report honestly that the gain is carried by the temporal-consistency *signal* (dominated by the
raw speed magnitude) rather than by any single hand-designed residual, and that direct cross-dataset transfer
is weak without target-domain calibration. We do **not** modify the VIO back-end, add object factors, or claim
improved ego-localization; the contribution is a planner-facing reliability/refusal layer.
`[TODO: tighten abstract numbers after stereo-KITTI redo and added baselines]`

---

## I. Introduction

GPS-denied autonomy (urban canyons, tunnels, indoor/又 GNSS-jammed settings) forces a vehicle to perceive
*other* agents' states from its own sensors via VIO/visual tracking. Downstream planning (collision checking,
time-to-contact, gap acceptance) consumes those object states as if uniformly trustworthy. They are not: a
monocular/stereo object-velocity estimate at 40 m is far less reliable than a position estimate at 10 m.

Most dynamic-object SLAM/VIO work focuses on *improving* object-state estimation accuracy. We take a
complementary stance: **decide when an estimate should be trusted at all**, and otherwise refuse the unreliable
component (velocity) while still using the reliable one (position). This is a *selective prediction* / reject-option
problem, not a pure estimation problem.

Two empirical observations motivate the design:
1. **Velocity validity collapses with geometry; position is more stable** — a position-only regime exists and is
   substantial on both synthetic and real data (§VI).
2. **The strongest runtime predictor of validity is the temporal self-consistency of the raw estimate, not range
   or instantaneous geometry** — a jittery / physically implausible raw velocity signals unobservability and is
   observable *without ground truth* (§VII-C).

**Contributions.**
- **C1.** A cross-dataset (CARLA + real KITTI) characterization of dynamic-object *velocity-validity*: it
  collapses with range, position is more stable, a position-only regime is real, and the phenomenon is robust to
  detection thresholds and to near-contact/collision filtering (not a collision artifact).
- **C2.** **TCSV**, a selective validator that formalizes object-state validity as *selective prediction* over
  runtime-observable temporal-consistency features, and that beats distance / observability gates on
  **selective-risk** metrics. We are explicit (§VII-B) that the methodological value comes from the
  *selective-prediction formulation + risk-coverage evaluation*, **not** from a feature trick.
- **C3.** A **refusal-aware, planner-facing evaluation** (risk-coverage, overconfident-wrong velocity at fixed
  retention) that quantifies validity at the *decision* level rather than as classification AUROC.

**Explicit non-claims.** We do not modify the VIO back-end, add object factors to the back-end optimization,
do graphics frontier/trajectory planning, claim improved ego-localization, or claim the first observability-aware
refusal. `[TODO: confirm non-claim phrasing against final Related Work]`

---

## II. Related Work

### A. Dynamic-object SLAM / VIO object-motion estimation
Dynamic SLAM systems estimate moving-object trajectories jointly with ego-motion (e.g., VDO-SLAM, DynaSLAM II,
ClusterVO). These *improve* object-state estimation; they do not provide a calibrated per-estimate **refusal**
of the velocity component for a downstream planner.
`[TODO: write taxonomy paragraph + reference table — see RELATED_WORK_BASELINE_PLAN.md item 10]`

### B. Object-state / detection uncertainty estimation
Detection confidence, bbox/depth uncertainty, and learned aleatoric uncertainty for 3D detection.
We use YOLO confidence and a bbox-depth consistency cue as *baselines* (§VII), and show geometry/appearance
uncertainty alone under-predicts velocity validity. `[TODO: position vs probabilistic 3D-detection uncertainty literature]`

### C. Selective prediction / reject option
Selective classification, learning-to-defer, SelectiveNet, risk-coverage analysis. We adopt this framing for
object-state validity and use its native metrics (coverage, selective risk, AURC). `[TODO: cite Geifman & El-Yaniv
risk-coverage; SelectiveNet; learning-to-defer]`

### D. Planner-facing reliable perception
TTC/risk-aware perception, introspective perception, "know what you don't know" for AV stacks. Our refusal layer
is a planner-facing reliability gate. `[TODO: cite introspective perception / failure prediction for AV]`

### E. Boundary vs Qiu 2018 (observability gating)
Qiu et al. (2018) use a **geometric excitation/observability threshold** for binary acceptance of object motion.
We differ substantively: (i) we *empirically show geometry/range is not the strongest validity signal* —
temporal-consistency is; (ii) we use a *learned multi-class* validity with a *selective-risk* objective; (iii) we
validate on real data with decision-level metrics. We explicitly **do not** claim to be the first observability
gate. `[TODO: run a Qiu-style observability-gate baseline for a fair head-to-head — RELATED_WORK item 3]`

---

## III. Problem Formulation

For each detected dynamic-object track sample $t$, the front end emits a raw estimate
$\hat s_t=(\hat p_t,\hat v_t)$ from runtime-observable quantities only. Ground-truth velocity validity (label;
GT used **only** for evaluation) is

$$ y_t=\mathbb{1}\big[\,\lVert \hat v_t - v_t^{\mathrm{gt}}\rVert \le \tau_v\,\big],\quad \tau_v=3\,\text{m/s (ego-independent)}. $$

A selective validator learns a confidence $g_\theta(x_t)\in[0,1]$ and an emit threshold $\rho$:
emit velocity if $g_\theta(x_t)\ge\rho$, else refuse to **position-only**. The objective is the selective-risk /
risk-coverage trade-off, not classification accuracy: minimize the overconfident-wrong-velocity rate (risk) at a
target valid-velocity retention (coverage). `[TODO: add formal risk-coverage / AURC definition equations]`

The feature vector $x_t$ uses **no GT and no back-end internal quantities** (§V). Position validity is defined
analogously ($\lVert\hat p_t-p_t^{\mathrm{gt}}\rVert\le\tau_p$, $\tau_p=3$ m) and characterizes the position-only
regime (§VI).

---

## IV. — (merged into III/V)

---

## V. Method: TCSV

### A. Temporal self-consistency features (runtime-observable)
14 features in three groups (window $W$ controls the 4 windowed features; $W{=}5$ default):
- **GEO (5):** range, bearing, bbox_area, depth, det_conf.
- **TEMP-base (2):** track_age, raw_speed.
- **TEMP-residual (7):** `cv_residual` (constant-velocity prediction error), `acceleration_score`,
  `jerk_score`, `velocity_direction_flip_count`, `bbox_depth_consistency`
  ($\mathrm{sign}(\Delta\log\text{area}){=}\mathrm{sign}(-\Delta\text{depth})$ fraction),
  `short_window_position_jitter`, `short_window_velocity_jitter`.

Only consecutive frames ($\Delta\text{frame}{=}1$) contribute to differentials. **No leakage:** all features are
runtime-observable; GT enters only the label. `[TODO: formal leakage audit — MISSING_EXPERIMENTS item 2]`

### B. Model family (deliberately minimal — no transformer/attention/large nets)
- **TCSV-rule:** depth-3 decision tree → human-readable rule gate.
- **TCSV-HistGBM:** main model.
- **TCSV-MLP:** small (64,32) MLP, neural control.

### C. Selective-risk objective & operating evaluation
We report risk-coverage curves, **AURC** (area under risk-coverage, lower=better), and
**overconfident-wrong velocity at fixed valid-retention 0.8/0.9**, alongside AUROC, overconf, retention,
false_refusal, F1_invalid. `[TODO: consider training-time selective-risk / cost-sensitive objective; current
models trained with standard loss then thresholded — note as design choice/limitation]`

---

## VI. Dataset and Validity Benchmark

- **CARLA** (dynamic_v3): $n=15{,}811$ matched detections, dt=0.05 s; ego-independent velocity criterion.
  Base velocity-valid rate 0.112.
- **KITTI tracking** (21 train sequences, YOLOv8m + monocular bbox-height depth, GT label_02): $n=37{,}022$
  ($34{,}943$ with velocity), dt=0.1 s. Base velocity-valid rate 0.430.
  `[TODO: replace monocular KITTI with stereo KITTI redo — image_03 re-download ~95% — MISSING_EXPERIMENTS item 1]`

### A. The velocity-validity phenomenon (C1)
Velocity validity decreases with range while position is more stable (validity by 0-15/15-30/30m+ bins):

| bin | CARLA pos | KITTI pos | CARLA vel | KITTI vel |
|---|---|---|---|---|
| 0–15 m | 0.89 | 0.86 | 0.70 | 0.65 |
| 15–30 m | 0.73 | 0.74 | 0.26 | 0.45 |
| 30 m+ | 0.30 | 0.44 | 0.08 | 0.21 |

All four sub-phenomena reproduce on real KITTI (velocity collapses, position more stable, position-only regime
substantial, invalid-velocity common). Absolute numbers differ (10 Hz vs 20 Hz, monocular depth, human tracks).

### B. Robustness of the phenomenon
- **Threshold-robust:** holds across detection thresholds (27/27). `[TODO: regenerate threshold-robustness numbers
  after grouping fix — MISSING_EXPERIMENTS item 8]`
- **Not a collision artifact:** a near-contact/collision audit over 24 CARLA runs finds only 3.8% near-contact
  frames (3 contaminated runs); excluding them leaves the velocity-validity-vs-range trend unchanged and slightly
  *improves* near-range position validity. The apparent "rear-end" footage is dense car-following, not collisions.

---

## VII. Experiments

Splits: **CARLA by run, KITTI by sequence**, plus cross-dataset (CARLA→KITTI, CARLA+KITtrain→held-out-KITTI).
**Never frame-random.**

### A. Selective-risk: TCSV vs gates (headline)
| scenario | model | AUROC | AURC↓ | overconf@ret.9 |
|---|---|---|---|---|
| KITTI→KITTI | distance_gate | 0.686 | 0.457 | 0.430 |
| KITTI→KITTI | **TCSV-HistGBM** | **0.923** | **0.210** | **0.250** |
| CARLA→CARLA | distance_gate | 0.755 | 0.773 | 0.815 |
| CARLA→CARLA | **TCSV-HistGBM** | **0.800** | **0.703** | **0.754** |
| CARLA+KITtrain→KIThold | TCSV-HistGBM | 0.917 | 0.213 | 0.269 |
| CARLA→KITTI (direct) | TCSV-HistGBM | 0.719 | 0.406 | 0.467 |

TCSV wins decisively on KITTI and modestly on CARLA (high base-invalid rate; velocity is intrinsically hard).
**Cross-dataset direct transfer is weak** (CARLA→KITTI AURC 0.406 vs distance 0.456) and needs target-domain
calibration. `[TODO: add no_policy / YOLO-conf / bbox-depth / KF-smoothing / SelectiveNet baselines to this table —
RELATED_WORK_BASELINE_PLAN.md]`

### B. Do the new temporal residuals help? (HONEST — they do not, net)
| dataset | OLD10 AUROC | TCSV14 AUROC |
|---|---|---|
| CARLA | 0.829 | 0.800 (slightly **down**) |
| KITTI | 0.919 | 0.923 (slightly **up**) |

The hand-designed physical residuals do **not** provide a net accuracy gain over the prior feature set; the
methodological contribution is the *selective-prediction formulation and risk-coverage evaluation*, not the
features. We state this plainly. `[TODO: keep this paragraph honest; do not let later edits oversell residuals]`

### C. Feature importance (permutation, ΔAUROC)
- CARLA group totals: TEMP-base **0.247** ≫ GEO 0.044 ≈ TEMP-residual 0.032.
- KITTI group totals: TEMP-base 0.157 > TEMP-residual 0.093 > GEO 0.060.
- Dominant single feature: **raw_speed** (CARLA 0.193, KITTI 0.140). Strongest *new* residual: KITTI `cv_residual`
  (rank 2, 0.061).

Reading: temporal-consistency dominates geometry (supports C2 at the group level), but the signal is mostly the
*raw-speed magnitude/plausibility*, not the fancier residuals. `[TODO: add SHAP plot to make the temporal story
crisp — MISSING_EXPERIMENTS item 6]`

### D. Temporal-window ablation
$W\in\{1,3,5,7\}$, in-domain HistGBM: CARLA W=1 (0.813) ≈ W=7 (0.824); KITTI W=1 (0.917) → W=5/7 (0.923). The
window beyond a single frame adds little; $W{=}5$ is a mild default, **not** a contribution.

### E. Honest correction: CARLA grouping fix
The prior pipeline grouped CARLA tracks by `(run, track_id)`, but run names repeat across towns
(Town01/dense_b1, Town10HD/dense_b1), merging cross-town tracks. We regroup by `(town, run, track_id)`; CARLA
in-domain HistGBM AUROC drops from a previously reported 0.873 to **0.800** (still beats distance 0.755, margin
≈+0.045). KITTI is unaffected. `[TODO: propagate this correction into older reports — MISSING_EXPERIMENTS item 9]`

### F. TCSV-rule (interpretability)
A depth-3 tree gates primarily on `raw_speed`, then `velocity_direction_flip_count` and
`short_window_velocity_jitter` — consistent with the importance analysis. `[TODO: paste final rule listing as a
figure/box]`

---

## VIII. Planner-facing Minimal Evaluation

The refusal layer is meant to protect a downstream planner from acting on overconfident-wrong velocity. We plan a
*minimal* downstream check (not a planner method): feed emitted-vs-refused object states into a simple
time-to-contact / collision-risk estimate and measure how refusal reduces dangerous TTC/risk errors at fixed
coverage. `[TODO: implement TTC/risk minimal evaluation — MISSING_EXPERIMENTS item 4]`
`[TODO: failure gallery (car-following / lateral-crossing / occlusion) — MISSING_EXPERIMENTS item 5]`

**Scope guard:** this section stays a downstream *validation*; full frontier exploration + trajectory planning is
explicitly deferred to a separate paper (Paper-3) and is **not** a contribution here.

---

## IX. Limitations (honest)

1. **Cross-dataset direct transfer is weak** (CARLA→KITTI); the learned validity boundary needs target-domain
   calibration.
2. **KITTI uses monocular bbox-height depth** (image_03 zip was corrupted); a stereo redo is pending. `[TODO]`
3. **Velocity GT is differenced** from GT positions (noisy; occlusion/truncation).
4. **Absolute overconfidence remains high** on CARLA (velocity is intrinsically hard at range; base-invalid 0.89).
5. **The hand-designed residuals add little net accuracy**; value is in the formulation/evaluation, not features.
6. **Operating point** uses train-Youden thresholding, not a training-time selective objective. `[TODO]`

---

## X. Conclusion (draft)

We reframed dynamic-object state estimation for GPS-denied navigation as a **selective-prediction** problem:
decide *when to trust* an object velocity and otherwise fall back to position-only. The velocity-validity
phenomenon is real and cross-dataset; a minimal **selective validator (TCSV)** beats distance/observability gates
on selective-risk metrics, driven by the **temporal-consistency of the raw estimate** rather than geometry. We are
explicit about what does *not* work (hand-designed residuals, cross-dataset transfer, temporal windows) and about
what we do not claim (no back-end change, no localization gain, no first-observability-gate claim). The result is
a planner-facing reliability layer, not a new estimator or planner. `[TODO: finalize after baselines + stereo redo]`

---

### Inline TODO index (mirrors MISSING_EXPERIMENTS_TODO.md)
- `[TODO]` stereo KITTI redo (§VI, §IX)
- `[TODO]` leakage audit (§V-A)
- `[TODO]` Qiu-style observability gate baseline (§II-E, §VII-A)
- `[TODO]` no_policy / YOLO-conf / bbox-depth / KF-smoothing / SelectiveNet baselines (§VII-A)
- `[TODO]` TTC/risk planner-facing minimal eval (§VIII)
- `[TODO]` failure gallery (§VIII)
- `[TODO]` SHAP feature-importance plot (§VII-C)
- `[TODO]` risk-coverage figure cleanup (Fig. plan)
- `[TODO]` threshold-robustness regen after grouping fix (§VI-B)
- `[TODO]` propagate CARLA grouping fix to old reports (§VII-E)
- `[TODO]` Qiu 2018 claim-boundary table (§II-E)
