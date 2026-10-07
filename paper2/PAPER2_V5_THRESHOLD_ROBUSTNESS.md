# PAPER2_V5_THRESHOLD_ROBUSTNESS (C1 — not a threshold artifact)

> Sweep 27 threshold combos (pos∈[2.0, 3.0, 5.0] m, speed∈[2.0, 3.0, 5.0] m/s, dir∈[30.0, 45.0, 60.0]°). Claims must hold across ALL combos to be reviewer-proof.

## Qualitative claims (count holding / total)
- **R1** velocity_valid < position_valid at every bin: **27/27**
- **R2** velocity_valid monotonically decreases with distance: **27/27**
- **R3** position_only ≥ 0.20 at mid/near range: **27/27**
- **R4** velocity_valid < 0.70 even at 0-15m (velocity unreliable up close): **27/27**

## Value ranges across all thresholds (stability of the headline numbers)
| quantity | 0-15m | 15-30m | 30m+ |
|---|---|---|---|
| velocity_valid range | [0.32, 0.43] | [0.11, 0.24] | [0.04, 0.11] |
| position_valid range | [0.55, 0.95] | [0.46, 0.83] | [0.21, 0.43] |
| position_only range | [0.29, 0.64] | [0.34, 0.73] | [0.19, 0.40] |

## Reading
- velocity-vs-distance collapse and velocity«position hold in 27/27 combos → the regime structure is **robust, not threshold-tuned**.
- absolute rates shift with thresholds (expected) but the ORDERING and COLLAPSE are invariant.
- the default (pos3/spd3/dir45) sits inside these ranges; all conclusions use ablatable thresholds.
