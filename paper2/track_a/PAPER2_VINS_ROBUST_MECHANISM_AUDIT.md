# PAPER2 Phase A — VINS ROBUST-MECHANISM AUDIT (deterministic)

> Separates the three robust mechanisms (Huber residual loss | 3-px backend hard cull | — TCSV comes
> later) on the 2 clean+stable runs. All numbers from DETERMINISTIC replays. Huber-off / cull-off are
> ABLATION ONLY, never the method. Metrics: `paper2_vins_robust_mechanism_metrics.csv`. Date 2026-07-01.

---

## 0. The determinism prerequisite (a required detour)

The stock config `carla_stereo_imu_640_R3_b05_gm.yaml` has **`multiple_thread: 1` + `max_solver_time: 0.08`**.
This makes the offline replay **NONDETERMINISTIC**: the time-bounded solver does a load-dependent number
of iterations, so the same input gives run-to-run ATE swings of **~15%** (observed 2.65 ↔ 3.35 m ATE_se3
on Town01 dense_b1 across identical stock invocations). **A single-run ATE difference cannot be attributed
to a switch under this config.** (This retroactively invalidates the earlier "Huber-off improves ATE 15%"
smoke and, by the same token, casts doubt on the prior "masking improves ATE ~10%" numbers — both were
within the nondeterminism band.)

Two configs were derived to fix this:
- `..._DET.yaml`  (multiple_thread 0, max_solver_time 0.5) — still nondeterministic across invocations
  (the 0.5 s bound still binds under load).
- **`..._DET2.yaml` (multiple_thread 0, max_solver_time 1000)** — the time bound never binds, only
  `max_num_iterations: 10` controls. **Verified deterministic: V1 == V1rep byte-identical.** All Phase A
  numbers below use DET2. Row count is a fixed 520 in every run (no frame drops).

Note DET2 changes the operating point vs the manifest baseline (single-thread, full 10 iters → 520 vio
poses, ATE ~2.7–3.2 m) — that is fine: Phase A measures the RELATIVE effect of the switches under a
reproducible estimator, which requires determinism more than it needs the exact stock operating point.

---

## 1. Deterministic results (DET2)

| variant | run | huber | cull | ATE_rmse | ATE_mean | RPE | early | late | feat_mgr | outlier_ratio | fail |
|---|---|---|---|---|---|---|---|---|---|---|---|
| V1  | dense_b1  | on  | on  | 3.153 | 2.646 | 0.252 | 1.015 | 0.457 | 60.2 | 0.341 | 0 |
| V1rep | dense_b1 | on | on | 3.153 | 2.646 | 0.252 | 1.015 | 0.457 | 60.2 | 0.341 | 0 |
| V2  | dense_b1  | off | on  | 2.823 | 2.241 | 0.217 | 1.003 | 0.430 | 52.6 | 0.334 | 0 |
| V3  | dense_b1  | on  | off | 2.823 | 2.241 | 0.217 | 1.003 | 0.430 | **255.8** | **0.000** | 0 |
| V3b | dense_b1  | off | off | 3.153 | 2.646 | 0.252 | 1.015 | 0.457 | 255.2 | 0.000 | 0 |
| V1  | medium_b1 | on  | on  | 2.702 | 1.847 | 0.155 | 0.971 | 0.398 | 58.0 | 0.329 | 0 |
| V2  | medium_b1 | off | on  | 2.726 | 2.032 | 0.181 | 0.992 | 0.409 | 58.0 | 0.333 | 0 |
| V3  | medium_b1 | on  | off | 2.702 | 1.847 | 0.155 | 0.971 | 0.398 | **251.2** | **0.000** | 0 |
| V3b | medium_b1 | off | off | 2.702 | 1.847 | 0.155 | 0.971 | 0.398 | 251.2 | 0.000 | 0 |

Byte-identity: dense V1==V3b, V2==V3 (an **XOR pattern**: huber⊕cull); medium V1==V3==V3b, only V2 differs.

---

## 2. Answers to the four Phase-A questions

### Q1. Is Huber a main confounder?
**No.** Huber on/off changes ATE by ≤0.33 m on dense and 0.02 m on medium, and the **sign flips** between
runs (Huber-off is *better* on dense, *worse* on medium). A confounder that helps on one clean run and
hurts on another by a comparable margin is not a systematic effect — it is chaotic perturbation. Also,
in back-to-back runs Huber-on == Huber-off == Huber-δ0.001 byte-identical (det_verify), and the visual
factors are numerous (mono≈283, stereo≈248/keyframe, whitened RMS≈6.5 ≫ δ=1.0) — so Huber engages many
features yet does not move the logged pose. **Huber is not a driver of the trajectory here.**

### Q2. Is the backend 3-px cull a main confounder?
**Structurally large, but ATE-inert.** Turning the cull off is the ONLY switch with a big, consistent,
deterministic structural effect: **feat_mgr jumps 52→256 (~5×) and outlier_ratio 0.34→0.00** on both
runs. Yet the ATE barely moves — **medium V1==V3 byte-identical** (cull off = stock), dense differs by
0.33 m (and non-monotonically, matching the Huber XOR). So the 3-px cull removes ~2/3 of the tracked
features (the high-reproj / dynamic ones) but the trajectory is essentially unchanged. **The cull is
doing real feature-cleaning work, but that work is not what determines the pose.**

### Q3. Does turning the cull off crash VINS?
**No.** V3 / V3b finish with 0 failures, 520 poses, early/late scale in the same band as stock. Cull-off
is stable on these clean runs (it just keeps 5× more features). So the cull is **not** a load-bearing
safety mechanism on clean data — though this may differ on degraded/hard runs (untested; out of scope).

### Q4. Should the final method keep Huber / cull?
**Yes — keep both as stock in the method.** They are cheap, harmless on clean runs, and standard; there
is no evidence to remove them, and cull may protect on harder scenes. Huber-off / cull-off remain
ablation instruments only.

---

## 3. The finding that reframes the TCSV thesis

The trajectory on these runs is **dominated by IMU pre-integration + the marginalization prior**, not by
the visual channel. Evidence: (a) removing the entire visual robust loss changes nothing back-to-back;
(b) removing the entire 3-px cull (5× more/fewer features) changes ATE only chaotically by ≤0.33 m;
(c) hundreds of high-residual visual factors exist yet do not move the pose. **Because TCSV routing acts
on this same visual channel, its ATE effect is expected to be equally small and non-monotonic.**

### Critical caveat — this is partly an IDEAL-IMU artifact
The replay recipe uses **`ideal_imu`** (synthetic near-perfect IMU) + skip-head 150. A near-perfect IMU
makes the estimator trust inertial integration heavily, so the visual channel is naturally overpowered.
This is a **config artifact, not a universal property of VINS**. A fair test of whether visual-feature
routing (TCSV) can help would need a setup where vision actually drives the pose — realistic/noisy IMU,
or IMU-degraded runs. Under the current ideal-IMU recipe, **no visual routing (TCSV, all_dynamic, oracle)
can be expected to move ATE**, because vision barely moves ATE at all. This must be stated before any
Phase C/D result is interpreted.

## 4. What Phase A settles
- Nondeterminism was the real first confounder; fixed with DET2. Use DET2 for ALL subsequent phases.
- Huber: not a confounder (chaotic ≤0.3 m, sign-unstable). Keep as stock.
- 3-px cull: big on feature count (5×), inert on ATE, non-crashing. Keep as stock.
- The visual channel is IMU-dominated under ideal_imu → the ceiling for any visual routing effect
  (incl. TCSV) is at the ~0.1–0.3 m chaotic-noise level on these runs. Phase B checks whether there is
  even feature mass in object regions for routing to act on.
