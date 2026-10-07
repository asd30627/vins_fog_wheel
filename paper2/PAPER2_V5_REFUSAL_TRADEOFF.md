# PAPER2_V5_REFUSAL_TRADEOFF (C3 — operating-point sweep)

> Sweep velocity-emit threshold. no-policy overconfidence (base invalid rate) = 0.839. Fig: figs/fig_v5_refusal_tradeoff.png

## Overconfident-wrong-velocity at matched valid-retention (lower = better)
| retention | v5_OVI | distance(-range) |
|---|---|---|
| 0.7 | 0.657 | 0.579 |
| 0.8 | 0.637 | 0.618 |
| 0.9 | 0.635 | 0.721 |

## Reading (honest)
- ANY observability-aware refusal cuts overconfidence massively from the no-policy 0.839 as retention drops — this is the validity-LAYER value (the framework), independent of OVI.
- v5_OVI vs distance: OVI lower-or-equal overconfidence at 1/3 retention levels → OVI roughly ties distance (consistent with the OVI ablation: geometric gain is small).
- HONEST: the headline C3 result is the validity-layer trade-off itself (huge overconfidence cut + position_only regime), NOT that OVI specifically beats a distance gate (that gain is marginal).
- v4-analog (uncertainty~range) is monotone-equivalent to the distance gate here, so it overlaps the distance curve.
