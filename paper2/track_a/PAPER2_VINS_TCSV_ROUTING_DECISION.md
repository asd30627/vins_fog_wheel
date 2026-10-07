# PAPER2 — VINS × TCSV ROUTING DECISION (after Phase A + B; STOP before C/D)

> Honest synthesis of Phase A (robust-mechanism ablation, deterministic) + Phase B (router logging).
> Phase C/D (hard routing / soft weighting) were NOT run — per instruction, STOP after A+B. Date 2026-07-01.

## Answers to the 9 questions

1. **Is VINS's Huber a main confounder?** — **No.** Under the deterministic DET2 config, Huber on/off
   changes ATE by ≤0.33 m and the **sign flips between the two clean runs** (better on dense, worse on
   medium); back-to-back it is byte-identical (on==off==δ0.001). Despite ~283 mono + ~248 stereo visual
   factors/keyframe with whitened RMS≈6.5 ≫ δ=1.0, the robust loss does not move the trajectory. Huber
   is not a driver. Keep it as stock; it is harmless.

2. **Is the backend 3-px cull a main confounder?** — **Structurally large, ATE-inert.** It is the only
   switch with a big deterministic structural effect (feat_mgr 52→256, ~5×; outlier_ratio 0.34→0), yet
   ATE barely moves (medium: cull-off == stock byte-identical; dense: 0.33 m, non-monotonic). It removes
   only **16.2%** of object-region features (Phase B) — it does NOT already clean dynamics. It does not
   crash when off. Keep as stock; not an ATE driver.

3. **Is TCSV-M actually used?** — **Yes as a signal, not yet as a VINS input.** The real TCSV-M(mono)
   (leak-free, leave-run-out) is scored per detection and logged against VINS features
   (`paper2_tcsv_vins_scores.csv`, `paper2_vins_router_logging.csv`) — NOT raw_speed. But **actual
   routing into the estimator (Phase C/D) was not run** (STOP after A+B). Phase B shows its deployable
   footprint is small: it would drop ~2.6% of features, and only ~11% of in-object features are even
   TCSV-scored (track_id=−1 coverage gap).

4. **Is TCSV-M better than raw_speed / all_dynamic?** — **GATED (Phase C not run).** Cannot be claimed.
   Note: on the ideal-IMU recipe no routing variant is expected to move ATE (Q7), so a fair comparison
   needs a vision-relevant setup first.

5. **Is TCSV-M soft more stable than hard routing?** — **GATED (Phase D not run).**

6. **Does it approach oracle?** — **GATED (oracle/Phase C not run).**

7. **Can we claim a VINS localization improvement?** — **No.** Two independent reasons:
   (a) On this recipe the visual channel is **ATE-inert** — the trajectory is IMU + marginalization
   dominated (ideal_imu artifact), so removing 2/3 of features (cull-off) or all robust loss changes ATE
   only chaotically (≤0.3 m, sign-unstable). (b) The earlier positive signals (masking −10%, Huber −15%)
   were inside the **nondeterminism band** of the stock config (±~15%) and do not survive determinism.
   TCSV touches only 2.6% of features → far below that floor.

8. **If not, state the honest ceiling.** — **We can claim a learned per-object state-validity signal
   (TCSV-M) for planner/perception-facing use; we CANNOT claim a VINS/VIO localization improvement.**
   The VINS line is, at most, **secondary/appendix evidence**, and even that is bounded: under the
   ideal-IMU replay the visual channel does not drive the pose, so no visual routing (TCSV, all_dynamic,
   or oracle) can be expected to improve localization on these runs.

9. **Is a dynamic-object factor worth the next stage?** — **Not yet — do NOT start it.** A dynamic-object
   BA factor also acts through the visual/landmark channel, which Phase A shows is inert under this
   recipe. Prerequisite before any dynamic factor is worthwhile: a setup where **vision actually drives
   the pose** — realistic/noisy IMU or explicit IMU degradation — re-run Phase A there and confirm the
   visual channel (and hence routing) has a deterministic ATE effect exceeding noise. Keep
   `PAPER2_DYNAMIC_OBJECT_FACTOR_FEASIBILITY.md` / `PAPER2_LEARNING_THROUGH_BA_FEASIBILITY.md` as design
   only (Phase E).

## What Phase A+B delivered
- Fixed a real **nondeterminism confound** (stock `multiple_thread=1`+`max_solver_time=0.08` → ±15% ATE);
  established the deterministic **DET2** config (verified V1==V1rep). All future replays must use it.
- Deterministic robust-mechanism ablation: Huber inert; 3-px cull big-on-count/inert-on-ATE/non-crashing;
  visual channel IMU-dominated (ideal-IMU caveat). `PAPER2_VINS_ROBUST_MECHANISM_AUDIT.md`.
- Router logging: 36.8% of features on objects (cull leaves 84% of them), TCSV deployable footprint 2.6%,
  with an ~11%-only TCSV-scoring coverage of in-object features. `PAPER2_VINS_ROUTER_LOGGING_AUDIT.md`.

## STOP
Per instruction: Phase A + B done → **STOP**. Do not run Phase C (hard routing) or D (soft weighting)
until裁示. Recommended next step is NOT C/D on this recipe (visual inert) but a **vision-relevant
operating point** (realistic IMU), then re-gate.
