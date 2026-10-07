# PAPER2 Part 1 — FRAME vs SEQUENCE DECISION (honest)

> Built from the actual bake-off (`PAPER2_FRAME_VS_SEQUENCE_RESULTS.md` + CSVs). CARLA 4 towns
> n=23,567; KITTI n=37,022. Splits by group (CARLA town@run, KITTI kitti@seq) — NO frame-random,
> no track in both train/test. Sequence windows PAST-ONLY (edge-pad earliest), no future leak, no
> centered window. Primary metric AURC↓. Bad/negative results reported as-is. Date 2026-07-01.

Selected: **BEST_PER_FRAME_MODEL = `TCSV-HistGBM-bal`**, **BEST_SEQUENCE_MODEL = `seq_pool_hgbm` (T=5, "full" pooling = mean/std/min/max/last/slope)**, by mean in-domain AURC.

---

## Numbers that drive every answer (mean in-domain AURC↓, CARLA→CARLA & KITTI→KITTI)

| family | model | mean in-dom AURC |
|---|---|---|
| sequence | **seq_pool_hgbm (T5,full)** | **0.479** |
| sequence | seq_pool_mlp | 0.503 |
| per-frame | **TCSV-HistGBM-bal** | **0.496** |
| per-frame | TCSV-M(mono) | 0.498 |
| per-frame | TCSV-HistGBM | 0.502 |
| per-frame | MLP(128,64) | 0.521 |
| sequence | seq_GRU | 0.527 |
| sequence | seq_TCN | 0.559 |
| sequence | seq_Transformer | 0.565 |
| per-frame | logistic | 0.542 |
| per-frame | cv_smoothing_gate | 0.579 |
| per-frame | distance_gate | 0.657 |

Paired bootstrap ΔAURC over groups (seq_pool_hgbm − TCSV-HistGBM-bal): CARLA→CARLA −0.0225 **[−0.051, +0.002] TIE**; KITTI→KITTI −0.0107 **[−0.018, −0.008] seq better**; C+Ktr→Khold −0.0057 **[−0.009, −0.003] seq better**; K+Ctr→Chold +0.0055 **[−0.007, +0.031] TIE**. Both learned families beat cv_gate everywhere (CI<0, Δ≈0.07–0.11).

---

## The 8 questions

### 1. Strongest per-frame model?
**`TCSV-HistGBM-bal`** (HistGBM with class-balanced sample weights) at 0.496 mean in-domain AURC —
but it is **statistically tied** with `TCSV-M(mono)` (0.498) and `TCSV-HistGBM` (0.502). For deployment
I recommend **`TCSV-M(mono)`**: same accuracy, plus monotone physical priors (interpretable, robust).
All three crush every gate (cv 0.579, distance 0.657) by a wide margin.

### 2. Strongest sequence model?
**`seq_pool_hgbm`** on **T=5, "full" temporal pooling** (mean/std/min/max/last/slope of 9 past-only
per-frame features → HistGBM). 0.479 mean in-domain AURC — best of all 13 models. The T×pool sweep
picked T=5,full for BOTH CARLA and KITTI (longer windows T=10/15 did not help; richer pooling did).

### 3. Does sequence clearly beat per-frame?
**No — the win is real but marginal and dataset-dependent.** seq_pool_hgbm is **significantly** better
than the best per-frame on **KITTI** (CI<0, Δ−0.011) and on mixed C+Ktr→Khold (Δ−0.006), but only a
**tie** on **CARLA** (Δ−0.022, CI crosses 0) and on K+Ctr→Chold. Practical gap ≈ 0.006–0.022 AURC.
The headline is not "sequence ≫ per-frame"; it is **"temporal evidence aggregation gives a small,
mostly-significant edge; the large gap is learned-vs-gate, not sequence-vs-frame."**

### 4. If pooling wins, is it past-only / leakage-free?
**Yes.** Each window for a labeled row at track-position p is frames [p−T+1 .. p], edge-padded with the
**earliest** available frame (never future). "full" pooling uses last-frame + backward stats only.
Verified in `sorted_windows()` — no centered window, no future frame. The deployable sequence model
sees only the object's own past.

### 5. Are deep sequence models worth it?
**No.** GRU (0.527), TCN (0.559), Transformer (0.565) are **all worse** than simple pooling (0.479) on
every in-domain/mixed split, and worse than the best per-frame model too. This reproduces the earlier
Track A negative result, now on 4 CARLA towns. **Order-agnostic pooling beats order-preserving encoders
at this data scale** → ordering carries little signal; deep sequence nets overfit. Negative result kept
as an insight: "why a sequence *encoder* is not needed here."

### 6. Which model goes into the VINS/VIO experiment (Part 2)?
**Per-frame `TCSV-M(mono)` (or TCSV-HistGBM) as the primary**, with seq_pool_hgbm as an optional upgrade.
Reasons: (a) the sequence edge is **not significant on CARLA**, which is exactly the Part-2 VIO dataset;
(b) per-frame produces a validity score **per detection per frame** — directly usable to mask/weight that
object's image region with zero track-history latency; (c) seq needs a T-frame buffer per track, adding
complexity for ~0 CARLA benefit. Keep cv_smoothing_gate as cold-start fallback (new tracks, <T frames).

### 7. Do we need position_valid + velocity_valid multi-label?
**Yes — feasible and useful.** Both labels are learnable: position_valid AUROC 0.74 (CARLA) / 0.96
(KITTI); full_state_valid AUROC 0.85 / 0.93. Because position validity degrades slower than velocity
validity with range, the **position_only** regime (trust position, distrust velocity) is real and
exploitable — this is the basis for Part-2 **component-wise routing** (position_valid object → usable as a
positional landmark/occupancy; velocity_valid → motion factor candidate; neither → reject).

### 8. Overfitting risk?
**Yes, and located precisely:** **cross-domain CARLA→KITTI, all learned models LOSE to cv_smoothing_gate**
(seq_pool 0.389, TCSV 0.409 vs cv **0.317**). In-domain is healthy. CARLA has only 4 towns, so models can
fit town-specific texture. Mitigations that work in the data: (a) **mixed training** recovers it
(C+Ktr→Khold: seq_pool 0.204 ≫ cv 0.284); (b) keep the **cv-gate fallback**; (c) report cross-domain
honestly rather than claim universal superiority.

---

## One-paragraph verdict
Temporal **pooling** (T=5, full) → HistGBM is the single best validity model and is past-only/leak-free,
but its edge over the best per-frame model (TCSV-M/HistGBM) is small and only significant on KITTI; deep
sequence encoders are a confirmed negative. The dominant, robust effect is **learned validity ≫ simple
gates in-domain**, with a clear **cross-domain caveat** (CARLA→KITTI loses to cv). For Part 2 we therefore
carry the **per-frame TCSV model** (per-detection score, low latency) with cv fallback, and we treat
**position vs velocity validity as separate routable channels**.
