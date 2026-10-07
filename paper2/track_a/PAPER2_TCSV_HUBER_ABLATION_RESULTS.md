# PAPER2 — TCSV × HUBER ABLATION RESULTS

> Live replay numbers. Recipe = b05_gm config + rate 0.5 + ideal_imu + skip-imu-head 150, CARLA OFF,
> Town01 dense_b1 (clean + stable baseline). Binary rebuilt with `REL_VISUAL_ROBUST_LOSS`.
> Metrics CSV: `paper2_tcsv_huber_ablation_metrics.csv`. Date 2026-07-01.
> STATUS: **smoke stage done (V1, V2)**. V3–V8 GATED on the bbox→feature router.

---

## Stage 0 — smoke (V1 stock, V2 Huber-off), Town01 dense_b1

| variant | routing | Huber | ATE_se3 | early | late | vio_rows | fail | mean outlier_ratio | mgr_feat |
|---|---|---|---|---|---|---|---|---|---|
| **V1** | none | **on** | 3.35 m | 1.015 | 0.511 | 268 | 0 | 0.518 | 52.4 |
| **V2** | none | **off** | **2.86 m** | 1.003 | 0.475 | 269 | 0 | 0.505 | 52.2 |

### Reads
1. **Switch is neutral at default.** V1 reproduces the historical baseline **bit-identical**
   (early 1.015, late 0.511, ATE 3.35 m, 268 rows) → the `REL_VISUAL_ROBUST_LOSS` edit does not perturb
   stock behavior. Only the env changed between V1/V2 in a deterministic pipeline, so the V2 delta is
   real, not noise.
2. **Huber-off does NOT diverge.** V2 finishes cleanly, 0 failures, 269 poses, early/late scale in the
   same regime as V1. → **The full Huber-off sweep (V7) is VIABLE.** Smoke gate PASSED.
3. **Huber's standalone protective value on this clean run is ~zero — mildly negative.** Removing Huber
   *slightly improved* ATE (3.35 → 2.86 m, −0.49 m / −15%). One run, single seed, and late-scale ≈ 0.5
   in both (IMU scale-drift dominates the absolute error), so **do not over-claim the −15%**; the robust
   conclusion is directional: Huber is not the thing keeping this run stable.
4. **The backend 3-px cull is the real robustness layer and is ~Huber-independent.** mean outlier_ratio
   is essentially unchanged (0.518 vs 0.505) with Huber on vs off — the discrete 3-px reprojection cull
   removes the same ~51% of features either way. (Note: the last-frame value is 0.91/0.96, which is where
   the earlier "~0.9" figure came from — a cherry-picked final frame; the sequence mean is ~0.51.)

### Consequence for the TCSV story
- The feared "TCSV gets eaten by Huber" is a **smaller** risk than expected on clean runs: Huber is
  near-inert here. The **real** confounder is the **3-px backend cull**, which already deletes ~51% of
  features (the dynamic ones among them). TCSV must beat *that*, not Huber.
- Because Huber-off is stable, the clean de-confounding test is the **3-px cull**, not Huber. Recommend
  adding a "3-px cull OFF" probe (the `//return;` in `outliersRejection`) to the matrix — it is the
  mechanism TCSV most overlaps. (Optional extension; flagged, not yet run.)

---

## Stage 1 — V3–V8 (routing variants): **GATED**
Needs the bbox→VINS-feature router (per-frame `feat_weight` from `paper2_tcsv_vins_scores.csv` → drop
(hard) or `feat_weight_` (soft)). Then run V3 all_dynamic, V4 raw_speed_gate, V5 TCSV hard, V6 TCSV
soft, V7 TCSV soft + Huber-off, V8 oracle, on Town01 dense_b1 + medium_b1. Pending裁示.
