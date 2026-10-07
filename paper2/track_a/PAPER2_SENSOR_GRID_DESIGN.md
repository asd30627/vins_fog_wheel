# PAPER2 Phase 1 — SENSOR GRID DESIGN (life gate)

> Grid to locate the operating zone where the vision channel actually influences VINS pose. Round 1 =
> IMU gyro grade only (runnable now). Round 2 = FOG (needs the 2 patches from the knob audit; design only,
> gated for裁示). Not a best-ATE hunt — a boundary map. Runs use DET2 (deterministic). Date 2026-07-01.

## Round 1 — IMU gyro grade (no FOG, no wheel; estimator config = DET2 stock noise)

| id | grade (gen_carla_grade_imu) | gyro arw / bias | role |
|---|---|---|---|
| **I0** | `ideal_imu` | 0 / 0 | **negative control** — expect vision inert (Phase A confirmed) |
| **I1** | `industrial_fog` | 0.03 / 0.3 | mid gyro — primary "does vision wake up?" |
| **I2** | `precision_mems` | 0.15 / 5.0 | degraded gyro stress — must still finish (else UNSTABLE) |
| (I1b) | `military_fog` | 0.003 / 0.01 | optional in-between if I0→I1 jump is too coarse |

Generation per sequence: `gen_carla_grade_imu.py --seq <rec> --grade <g>` → `imu_grade_<g>.csv`; then
`make_player_imu_yref.py --skip-imu-head 150` → `imu_grade_<g>_yref.csv`; player consumes that file.
Estimator IMU noise left at stock (acc_n .1 / gyr_n .01) — the physically-honest "same estimator, worse
sensor" test. (An estimator-trust sweep is a separate knob, not mixed in here.)

**Known limitation carried from Phase 0:** the injector degrades **gyro only; accel stays clean**. So
Round 1 can only open the **rotation/yaw** channel; translation/scale stays accel+marg-pinned. If even I2
leaves vision inert on ATE, that is the signature of the clean-accel confound → the **accel-degradation
patch** becomes the required next lever (gated for裁示). We therefore report BOTH ATE and a
rotation-sensitive read (RPE, late-scale, yaw) so a rotation-only vision effect is not missed.

## Round 2 — FOG (DESIGN ONLY — needs patches, gated)
| id | FOG | needs |
|---|---|---|
| F0 | none | — (Round 1 is F0) |
| F1 | low/noisy FOG | player `/fog/yaw` publisher + `fog_arw_` large |
| F2 | medium FOG | idem, mid `fog_arw_` |
| F3 | high-grade FOG | idem, small `fog_arw_` (tight, dominates yaw) |

Two patches required first (knob audit §C): (1) player publishes `/fog/yaw` from `fog_synth.csv`; (2)
`fog_arw_` exposed via env/YAML. FOG intentionally deferred: too-strong FOG re-pins yaw and would mask
vision again — Round 2 maps the FOG boundary only AFTER Round 1 shows a vision-active IMU zone.

## Runs & determinism
- Sequences: **Town01 dense_b1, medium_b1** (clean + stable). Others only if a baseline proves stable.
- Config: **DET2** for every run; strictly sequential (no parallel vins_node).
- Each setting first passes a **deterministic-repeat** check (a run == its repeat, byte-identical) before
  any variant delta is trusted. If a setting is nondeterministic, STOP and fix — no single-run conclusions.

## What Round 1 feeds into Phase 2
For each of I0/I1/I2 × {dense_b1, medium_b1}: run the vision-sensitivity probes (baseline, feature
dropout, all-object mask, oracle mask, cull-off) and classify VISION_INERT / VISION_ACTIVE / UNSTABLE.
Only VISION_ACTIVE settings advance to the Phase 3 life gate (TCSV routing).
