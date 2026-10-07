# PAPER2 Phase -4 — CLEAN BENCHMARK MANIFEST

> Which CARLA dynamic_v3 runs may enter which experiment, from the Phase -1 quality audit. Date 2026-07-01.
> Gate: only PASS_CORE -> core results; LOW_YIELD -> appendix/robustness; INVALID -> excluded (re-record after spawn fix).

## Tally: 25 PASS_CORE · 6 LOW_YIELD · 17 INVALID (of 48)

## CORE set (PASS_CORE) — usable for object-validity / VINS-masking / TTC
| run | matched | m<50m | tracks | dyn | use validity/mask/ttc |
|---|---|---|---|---|---|
| Town01/dense_b1 | 1180 | 777 | 31 | 60 | 1/1/1 |
| Town01/dense_r30 | 872 | 717 | 13 | 59 | 1/1/1 |
| Town01/dense_r60 | 1002 | 873 | 13 | 59 | 1/1/1 |
| Town01/dense_r90 | 482 | 267 | 19 | 60 | 1/1/1 |
| Town01/medium_b1 | 1006 | 865 | 17 | 40 | 1/1/1 |
| Town01/medium_r30 | 675 | 640 | 6 | 39 | 1/1/1 |
| Town01/medium_r60 | 569 | 491 | 13 | 40 | 1/1/1 |
| Town01/sparse_r60 | 885 | 605 | 18 | 15 | 1/1/1 |
| Town06/dense_b1 | 841 | 372 | 25 | 70 | 1/1/1 |
| Town06/medium_b1 | 861 | 330 | 14 | 50 | 1/1/1 |
| Town06/medium_r30 | 511 | 238 | 9 | 49 | 1/1/1 |
| Town06/sparse_b1 | 1238 | 506 | 23 | 25 | 1/1/1 |
| Town07/dense_r60 | 766 | 535 | 5 | 69 | 1/1/1 |
| Town07/dense_r90 | 850 | 519 | 20 | 70 | 1/1/1 |
| Town07/medium_r90 | 447 | 308 | 17 | 50 | 1/1/1 |
| Town07/sparse_r90 | 295 | 222 | 7 | 25 | 1/1/0 |
| Town10HD/dense_b1 | 2017 | 1443 | 47 | 60 | 1/1/1 |
| Town10HD/dense_r30 | 1562 | 1268 | 39 | 59 | 1/1/1 |
| Town10HD/dense_r60 | 407 | 291 | 15 | 59 | 1/1/1 |
| Town10HD/dense_r90 | 1610 | 1169 | 23 | 60 | 1/1/1 |
| Town10HD/medium_b1 | 507 | 486 | 11 | 40 | 1/1/1 |
| Town10HD/medium_r30 | 862 | 767 | 35 | 39 | 1/1/1 |
| Town10HD/medium_r90 | 961 | 692 | 32 | 40 | 1/1/1 |
| Town10HD/sparse_b1 | 375 | 212 | 6 | 15 | 1/1/1 |
| Town10HD/sparse_r90 | 487 | 339 | 17 | 15 | 1/1/1 |

## APPENDIX set (LOW_YIELD) — robustness only, not headline
| run | matched | m<50m | reason |
|---|---|---|---|
| Town01/medium_r90 | 351 | 228 | thin (few near objects) |
| Town07/dense_r30 | 6 | 6 | thin (few near objects) |
| Town07/medium_b1 | 312 | 82 | thin (few near objects) |
| Town07/medium_r30 | 42 | 39 | thin (few near objects) |
| Town07/medium_r60 | 297 | 247 | thin (few near objects) |
| Town07/sparse_b1 | 74 | 10 | thin (few near objects) |

## EXCLUDED set (INVALID) — re-record after spawn fix (Phase -3)
| run | reason |
|---|---|
| Town01/sparse_b1 | matched=0, 96% >150m, no near in-FOV |
| Town01/sparse_r30 | matched=1, 96% >150m, no near in-FOV |
| Town01/sparse_r90 | matched=0, 100% >150m, no near in-FOV |
| Town06/dense_r30 | 95% >150m |
| Town06/dense_r60 | 98% >150m |
| Town06/dense_r90 | matched=0, 99% >150m, no near in-FOV |
| Town06/medium_r60 | matched=0, 100% >150m, no near in-FOV |
| Town06/medium_r90 | matched=0, 100% >150m, no near in-FOV |
| Town06/sparse_r30 | YOLO det=0, matched=0, 99% >150m, no near in-FOV |
| Town06/sparse_r60 | matched=0, 100% >150m, no near in-FOV |
| Town06/sparse_r90 | matched=0, 100% >150m, no near in-FOV |
| Town07/dense_b1 | spawn-collision 56% |
| Town07/sparse_r30 | no near in-FOV |
| Town07/sparse_r60 | matched=2, no near in-FOV |
| Town10HD/medium_r60 | matched=0, no near in-FOV |
| Town10HD/sparse_r30 | matched=0 |
| Town10HD/sparse_r60 | matched=0, no near in-FOV |

## Usability by experiment (core set only)
- object validity: 25 runs
- VINS masking: 25 runs
- TTC / planner: 24 runs

## VINS-masking core (stable baseline REQUIRED — see Phase 1 audit)
- Town01 dense_b1, Town01 medium_b1 = confirmed stable baseline (early~1.0, ATE<4m). USE for core VINS.
- Town06 dense_b1 = PASS_CORE data but UNSTABLE baseline (ATE 41m, 84% far) -> failure-analysis only.
- Other PASS_CORE runs: VINS baseline stability not yet verified -> verify before core VINS use.

## Re-record priority (Phase -3), after spawn fix
1. Town06 sparse/medium/dense rotated (7 INVALID) — worst town, needs ego-relative spawn most.
2. Town01 sparse (3 INVALID) — sparse spawns too far.
3. Town07 dense_b1 (spawn collision) — needs min-distance guard.
4. Town10HD/Town07 sparse/medium rotated (remaining INVALID).
Do NOT re-record PASS_CORE runs. Preview-gate every re-record.
