# PAPER2 Life Gate Phase 2 — Results

> ideal_imu vs industrial_fog + object masking on Town06/07 R6 cores.
> DET2 config, 3 reps each condition, median ATE reported.
> Date 2026-07-01.

## t06 (Town06__dynamic_v3fix__rundense_near_r6_core)

| grade | variant | median_ATE (m) | Δ vs baseline | n_good_reps | verdict |
|---|---|---|---|---|---|
| ideal_imu | baseline | 34.73 | +0.0% | 3/3 | BASELINE (3/3 reps) |
| ideal_imu | all_object_mask | 34.53 | -0.6% | 3/3 | NO_SIGNAL |
| ideal_imu | random_control | 34.24 | -1.4% | 3/3 | NO_SIGNAL |
| industrial_fog | baseline | 36.99 | +0.0% | 3/3 | BASELINE (3/3 reps) |
| industrial_fog | all_object_mask | 36.80 | -0.5% | 3/3 | NO_SIGNAL |
| industrial_fog | random_control | 36.48 | -1.4% | 3/3 | NO_SIGNAL |

## t07 (Town07__dynamic_v3fix__rundense_near_r6_core)

| grade | variant | median_ATE (m) | Δ vs baseline | n_good_reps | verdict |
|---|---|---|---|---|---|
| ideal_imu | baseline | 32.74 | +0.0% | 3/3 | BASELINE (3/3 reps) |
| ideal_imu | all_object_mask | 32.74 | +0.0% | 3/3 | NO_SIGNAL |
| ideal_imu | random_control | 32.74 | +0.0% | 3/3 | NO_SIGNAL |
| industrial_fog | baseline | 34.91 | +0.0% | 3/3 | BASELINE (3/3 reps) |
| industrial_fog | all_object_mask | 34.91 | +0.0% | 3/3 | NO_SIGNAL |
| industrial_fog | random_control | 34.91 | +0.0% | 3/3 | NO_SIGNAL |

## Life Gate Classification

| town | grade | object_mask_Δ% | random_ctrl_Δ% | verdict |
|---|---|---|---|---|
| t06 | ideal_imu | -0.6% | -1.4% | VISION_INERT |
| t06 | industrial_fog | -0.5% | -1.4% | VISION_INERT |
| t07 | ideal_imu | +0.0% | +0.0% | VISION_INERT |
| t07 | industrial_fog | +0.0% | +0.0% | VISION_INERT |

## Notes

- VISION_ACTIVE: object_mask reduces ATE ≥5% AND random_control is neutral (Δ < −3%).
- VISION_INERT: masking makes no difference (<5% ATE change). Sensor dominates.
- Scale drift (late≈2.2) is consistent/deterministic across all conditions in these towns;
  relative Δ% is valid for comparison (same drift, same baseline).
- All runs: DET2 (max_solver_time=1000, multiple_thread=0), rate=0.5, skip-imu-head=150.

CSV: `paper2/track_a/paper2_life_gate_phase2.csv`
