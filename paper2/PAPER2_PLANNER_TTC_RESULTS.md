# PAPER2_PLANNER_TTC_RESULTS

> Minimal planner-facing eval (NOT a planner). CARLA front objects (body_fwd>0, |lat|<2.5 m), n=4043. TTC=range/closing-rate; risk if TTC<3.0s. GT range-rate from gt_range_m. Compares always-emit vs TCSV refusal at matched coverage (rates among EMITTED).

| policy | coverage | false_alarm | missed_risk | overconf_vel_accepted | n_emit |
|---|---|---|---|---|---|
| always_emit | 1.0 | 0.200 | 0.024 | 0.214 | 4043 |
| TCSV_emit@cov0.9 | 0.9 | 0.168 | 0.025 | 0.182 | 3638 |
| TCSV_emit@cov0.8 | 0.8 | 0.140 | 0.028 | 0.156 | 3234 |
| TCSV_emit@cov0.7 | 0.7 | 0.145 | 0.030 | 0.162 | 2830 |

## Reading (supports C3?)
- always-emit: overconfident invalid velocities that FLIP the TTC decision = **0.214**.
- TCSV refusal at coverage≈0.7: drops to **0.162** (reduces planner-accepted bad velocity).
- missed_risk is the safety-critical error; report whether refusal trades false_alarm/coverage for fewer planner-accepted bad velocities. Honest: refusal removes velocity, so missed_risk via velocity can only be addressed by falling back to position-only TTC `[TODO: position-only TTC variant]`.
- KITTI TTC: `[TODO: needs clean per-frame GT range; not computed here]`.

## Caveats
- This is a *minimal* decision-level probe, NOT a planning method (red line: no trajectory planning).
- TTC uses range-rate, not full relative-velocity vectors; a richer TTC is future work.
