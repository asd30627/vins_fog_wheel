# PAPER2_FAILURE_GALLERY

> Data-driven regime stratification (validity + TCSV selective-risk per regime). Image thumbnails NOT attached — raw frames for the KITTI tracking split / CARLA runs are not in the workspace `[TODO: attach representative frames]`.

| regime | n | base_invalid | pos_only_rate | TCSV AURC↓ | TCSV OC@ret.9 |
|---|---|---|---|---|---|
| car_following (CARLA) | 4058 | 0.848 | 0.401 | 0.628 | 0.674 |
| lateral_crossing (CARLA) | 9 | 0.556 | 0.222 | 0.329 | 0.556 |
| far_range>=30m (CARLA) | 7423 | 0.948 | 0.368 | 0.821 | 0.672 |
| position_only (CARLA) | 6458 | 1.000 | — | — | — |
| lateral_crossing (KITTI) | 89 | 0.663 | 0.483 | 0.323 | 0.206 |
| far_range>=30m (KITTI) | 10771 | 0.811 | 0.364 | 0.569 | 0.564 |
| occlusion/trunc (KITTI) | 24116 | 0.625 | 0.383 | 0.301 | 0.298 |
| position_only (KITTI) | 13206 | 1.000 | — | — | — |

## Reading
- `position_only` regimes confirm the C1 'use position, refuse velocity' regime is populated.
- High base_invalid + high AURC regimes (far range, occlusion) are where refusal matters most.
- Honest: where TCSV AURC stays high (hard regimes), the model also struggles — refusal there means frequent position-only fallback, not a velocity rescue.
- Figure: figs/failure_gallery/fig_regime_risk.png
- `[TODO]` attach 2–3 representative frames per regime once tracking images are staged.
