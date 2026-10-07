# PAPER2_CARLA_COLLISION_AUDIT

> Near-contact / collision audit over 24 dynamic_v3 runs. Front object = ego-body fwd>0, |lateral|<2.5 m. near_contact flag = front_range<3.0 m OR overlap(<4.5 m) OR hard-brake(>3.0 m/s drop).
> Overall near-contact frame ratio = **0.038**.

## Per-run
| town | run | n | min_front_range | frac<2m | frac<3m | frac_overlap | hard_brakes |
|---|---|---|---|---|---|---|---|
| Town01 | dense_b1 | 560 | 9.37 | 0.0 | 0.0 | 0.0 | 0 |
| Town01 | dense_r30 | 560 | 3.49 | 0.0 | 0.0 | 0.5 | 1 |
| Town01 | dense_r60 | 560 | 12.94 | 0.0 | 0.0 | 0.0 | 0 |
| Town01 | dense_r90 | 560 | 23.71 | 0.0 | 0.0 | 0.0 | 0 |
| Town01 | medium_b1 | 560 | 10.1 | 0.0 | 0.0 | 0.0 | 0 |
| Town01 | medium_r30 | 560 | 8.78 | 0.0 | 0.0 | 0.0 | 0 |
| Town01 | medium_r60 | 560 | 92.76 | 0.0 | 0.0 | 0.0 | 0 |
| Town01 | medium_r90 | 560 | 11.84 | 0.0 | 0.0 | 0.0 | 0 |
| Town01 | sparse_b1 | 560 | nan | 0.0 | 0.0 | 0.0 | 0 |
| Town01 | sparse_r30 | 560 | 129.91 | 0.0 | 0.0 | 0.0 | 0 |
| Town01 | sparse_r60 | 560 | 91.5 | 0.0 | 0.0 | 0.0 | 0 |
| Town01 | sparse_r90 | 560 | nan | 0.0 | 0.0 | 0.0 | 0 |
| Town10HD | dense_b1 | 560 | 2.86 | 0.0 | 0.004 | 0.339 | 0 |
| Town10HD | dense_r30 | 560 | 5.04 | 0.0 | 0.0 | 0.0 | 0 |
| Town10HD | dense_r60 | 560 | 18.16 | 0.0 | 0.0 | 0.0 | 0 |
| Town10HD | dense_r90 | 560 | 3.49 | 0.0 | 0.0 | 0.073 | 0 |
| Town10HD | medium_b1 | 560 | 10.32 | 0.0 | 0.0 | 0.0 | 0 |
| Town10HD | medium_r30 | 560 | 4.61 | 0.0 | 0.0 | 0.0 | 1 |
| Town10HD | medium_r60 | 560 | nan | 0.0 | 0.0 | 0.0 | 0 |
| Town10HD | medium_r90 | 560 | 24.62 | 0.0 | 0.0 | 0.0 | 0 |
| Town10HD | sparse_b1 | 560 | 19.66 | 0.0 | 0.0 | 0.0 | 0 |
| Town10HD | sparse_r30 | 560 | 92.42 | 0.0 | 0.0 | 0.0 | 0 |
| Town10HD | sparse_r60 | 560 | nan | 0.0 | 0.0 | 0.0 | 0 |
| Town10HD | sparse_r90 | 560 | 24.16 | 0.0 | 0.0 | 0.0 | 0 |

## Contaminated runs (min_front_range<4.5m OR >10% frames <3m)
- 3 runs: Town01/dense_r30, Town10HD/dense_b1, Town10HD/dense_r90

## Reading
- 3.8% of frames are near-contact → re-run C1/C3 excluding these (see paper2_carla_nearcontact_frames.csv).
- if excluding them changes the velocity-validity-vs-distance trend materially, the near range was contaminated;
  if the trend persists, the phenomenon is not a collision artifact.
