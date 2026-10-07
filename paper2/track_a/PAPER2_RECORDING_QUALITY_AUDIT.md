# PAPER2 Phase -1 — CARLA RECORDING / SPAWN QUALITY AUDIT

> Per-run object-visibility + detectability audit over 48 dynamic_v3 recordings (4 towns × 12 runs). Ego excluded from per_instance (range<2.0 m). FOV from ego yaw + camera fov. Date 2026-07-01.

## Classification summary
- **PASS_CORE**: 25  ·  **LOW_YIELD**: 6  ·  **INVALID_RECORDING**: 17

Gate rules — INVALID: frames incomplete OR det=0 OR matched<5 OR >95% objects beyond 150 m OR in-FOV-near objects <0.05/frame. PASS_CORE: matched≥150 & det/frame≥0.5 & matched<50m≥30 & dynamic≥1 & bbox_med≥100 px² & tracks≥5. else LOW_YIELD.

## Per-run (sorted town, then run)
| run | class | frames | gt_obj/f | rng_med | %<50m | %>150m | infov_near/f | det | matched | m<50m | bbox_med | tracks | dyn | use:validity/mask/ttc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Town01/dense_b1 | PASS_CORE | 560 | 60.0 | 216.7 | 5.2 | 71.7 | 1.81 | 1291 | 1180 | 777 | 691.3 | 31 | 60 | 1/1/1 |
| Town01/dense_r30 | PASS_CORE | 560 | 59.0 | 191.0 | 11.3 | 58.8 | 2.44 | 1143 | 872 | 717 | 686.4 | 13 | 59 | 1/1/1 |
| Town01/dense_r60 | PASS_CORE | 560 | 59.0 | 187.9 | 7.1 | 68.5 | 2.75 | 1293 | 1002 | 873 | 1101.9 | 13 | 59 | 1/1/1 |
| Town01/dense_r90 | PASS_CORE | 560 | 60.0 | 172.3 | 8.3 | 59.2 | 0.63 | 565 | 482 | 267 | 737.6 | 19 | 60 | 1/1/1 |
| Town01/medium_b1 | PASS_CORE | 560 | 40.0 | 217.8 | 6.4 | 71.9 | 1.73 | 1094 | 1006 | 865 | 882.7 | 17 | 40 | 1/1/1 |
| Town01/medium_r30 | PASS_CORE | 560 | 39.0 | 200.4 | 12.4 | 64.3 | 1.33 | 706 | 675 | 640 | 585.2 | 6 | 39 | 1/1/1 |
| Town01/medium_r60 | PASS_CORE | 560 | 40.0 | 164.0 | 10.2 | 57.4 | 1.37 | 661 | 569 | 491 | 992.4 | 13 | 40 | 1/1/1 |
| Town01/medium_r90 | LOW_YIELD | 560 | 40.0 | 185.6 | 12.4 | 63.9 | 0.78 | 364 | 351 | 228 | 277.4 | 3 | 40 | 0/1/1 |
| Town01/sparse_b1 | INVALID_RECORDING | 560 | 15.0 | 252.1 | 0.0 | 96.5 | 0.0 | 6 | 0 | 0 | 338.0 | 0 | 15 | 0/0/0 |
| Town01/sparse_r30 | INVALID_RECORDING | 560 | 15.0 | 276.2 | 0.0 | 96.3 | 0.0 | 5 | 1 | 0 | 86.8 | 1 | 15 | 0/0/0 |
| Town01/sparse_r60 | PASS_CORE | 560 | 15.0 | 118.7 | 20.5 | 35.6 | 1.87 | 1025 | 885 | 605 | 986.2 | 18 | 15 | 1/1/1 |
| Town01/sparse_r90 | INVALID_RECORDING | 560 | 15.0 | 277.2 | 0.0 | 100.0 | 0.0 | 5 | 0 | 0 | 2587.7 | 0 | 15 | 0/0/0 |
| Town06/dense_b1 | PASS_CORE | 720 | 70.0 | 237.8 | 2.2 | 83.9 | 1.4 | 856 | 841 | 372 | 329.5 | 25 | 70 | 1/1/1 |
| Town06/dense_r30 | INVALID_RECORDING | 720 | 69.0 | 407.5 | 0.7 | 95.0 | 0.47 | 541 | 450 | 201 | 297.5 | 14 | 69 | 1/1/0 |
| Town06/dense_r60 | INVALID_RECORDING | 720 | 69.0 | 541.4 | 0.7 | 97.5 | 0.44 | 327 | 272 | 162 | 1124.6 | 4 | 69 | 0/1/0 |
| Town06/dense_r90 | INVALID_RECORDING | 720 | 70.0 | 461.7 | 0.0 | 98.8 | 0.0 | 3 | 0 | 0 | 1002.7 | 0 | 70 | 0/0/0 |
| Town06/medium_b1 | PASS_CORE | 720 | 50.0 | 259.6 | 2.9 | 79.8 | 1.38 | 881 | 861 | 330 | 436.6 | 14 | 50 | 1/1/1 |
| Town06/medium_r30 | PASS_CORE | 720 | 49.0 | 396.6 | 1.2 | 92.4 | 0.58 | 727 | 511 | 238 | 766.3 | 9 | 49 | 1/1/1 |
| Town06/medium_r60 | INVALID_RECORDING | 720 | 50.0 | 528.2 | 0.0 | 100.0 | 0.0 | 7 | 0 | 0 | 1069.3 | 0 | 50 | 0/0/0 |
| Town06/medium_r90 | INVALID_RECORDING | 720 | 50.0 | 467.9 | 0.0 | 100.0 | 0.0 | 3 | 0 | 0 | 928.6 | 0 | 50 | 0/0/0 |
| Town06/sparse_b1 | PASS_CORE | 720 | 25.0 | 148.6 | 6.4 | 49.6 | 1.49 | 1270 | 1238 | 506 | 293.9 | 23 | 25 | 1/1/1 |
| Town06/sparse_r30 | INVALID_RECORDING | 720 | 25.0 | 320.3 | 0.0 | 98.7 | 0.0 | 0 | 0 | 0 | nan | 0 | 25 | 0/0/0 |
| Town06/sparse_r60 | INVALID_RECORDING | 720 | 25.0 | 618.9 | 0.0 | 100.0 | 0.0 | 6 | 0 | 0 | 1025.2 | 0 | 25 | 0/0/0 |
| Town06/sparse_r90 | INVALID_RECORDING | 720 | 25.0 | 567.1 | 0.0 | 100.0 | 0.0 | 6 | 0 | 0 | 1166.4 | 0 | 25 | 0/0/0 |
| Town07/dense_b1 | INVALID_RECORDING | 720 | 70.0 | 147.0 | 16.1 | 48.0 | 2.06 | 864 | 475 | 441 | 283038.2 | 11 | 70 | 1/1/1 |
| Town07/dense_r30 | LOW_YIELD | 720 | 69.0 | 160.2 | 2.4 | 53.7 | 0.07 | 6 | 6 | 6 | 278.5 | 3 | 69 | 0/0/0 |
| Town07/dense_r60 | PASS_CORE | 720 | 69.0 | 172.9 | 3.9 | 62.3 | 1.17 | 844 | 766 | 535 | 572.9 | 5 | 69 | 1/1/1 |
| Town07/dense_r90 | PASS_CORE | 720 | 70.0 | 143.5 | 8.1 | 47.0 | 1.39 | 935 | 850 | 519 | 800.0 | 20 | 70 | 1/1/1 |
| Town07/medium_b1 | LOW_YIELD | 720 | 50.0 | 139.3 | 14.5 | 44.8 | 0.79 | 349 | 312 | 82 | 1610.8 | 11 | 50 | 1/1/1 |
| Town07/medium_r30 | LOW_YIELD | 720 | 49.0 | 155.7 | 3.2 | 51.4 | 0.06 | 44 | 42 | 39 | 275.2 | 3 | 49 | 0/1/0 |
| Town07/medium_r60 | LOW_YIELD | 720 | 50.0 | 173.1 | 2.8 | 63.7 | 0.45 | 338 | 297 | 247 | 1888.1 | 6 | 49 | 1/1/0 |
| Town07/medium_r90 | PASS_CORE | 720 | 50.0 | 149.1 | 8.3 | 49.5 | 0.58 | 545 | 447 | 308 | 712.4 | 17 | 50 | 1/1/1 |
| Town07/sparse_b1 | LOW_YIELD | 720 | 25.0 | 130.0 | 14.1 | 41.0 | 0.06 | 195 | 74 | 10 | 390.1 | 5 | 25 | 1/0/0 |
| Town07/sparse_r30 | INVALID_RECORDING | 720 | 25.0 | 130.1 | 4.2 | 41.8 | 0.03 | 20 | 17 | 17 | 265.4 | 2 | 25 | 0/0/0 |
| Town07/sparse_r60 | INVALID_RECORDING | 720 | 25.0 | 168.8 | 0.0 | 67.7 | 0.0 | 5 | 2 | 1 | 917.2 | 1 | 25 | 0/0/0 |
| Town07/sparse_r90 | PASS_CORE | 720 | 25.0 | 138.9 | 12.6 | 43.4 | 0.25 | 409 | 295 | 222 | 639.3 | 7 | 25 | 1/1/0 |
| Town10HD/dense_b1 | PASS_CORE | 560 | 60.0 | 103.3 | 17.4 | 18.2 | 3.63 | 2273 | 2017 | 1443 | 740.9 | 47 | 60 | 1/1/1 |
| Town10HD/dense_r30 | PASS_CORE | 560 | 59.0 | 80.7 | 15.5 | 1.3 | 3.83 | 2126 | 1562 | 1268 | 1309.6 | 39 | 59 | 1/1/1 |
| Town10HD/dense_r60 | PASS_CORE | 560 | 59.0 | 132.1 | 3.8 | 39.2 | 0.63 | 702 | 407 | 291 | 770.2 | 15 | 59 | 1/1/1 |
| Town10HD/dense_r90 | PASS_CORE | 560 | 60.0 | 112.0 | 9.1 | 30.5 | 2.81 | 1834 | 1610 | 1169 | 691.0 | 23 | 60 | 1/1/1 |
| Town10HD/medium_b1 | PASS_CORE | 560 | 40.0 | 114.4 | 10.5 | 26.3 | 1.25 | 1081 | 507 | 486 | 608.5 | 11 | 40 | 1/1/1 |
| Town10HD/medium_r30 | PASS_CORE | 560 | 39.0 | 93.0 | 16.3 | 4.5 | 3.29 | 1298 | 862 | 767 | 3048.4 | 35 | 39 | 1/1/1 |
| Town10HD/medium_r60 | INVALID_RECORDING | 560 | 40.0 | 165.6 | 2.5 | 57.4 | 0.0 | 272 | 0 | 0 | 770.0 | 0 | 40 | 0/0/0 |
| Town10HD/medium_r90 | PASS_CORE | 560 | 40.0 | 111.3 | 11.5 | 26.9 | 1.87 | 1086 | 961 | 692 | 911.3 | 32 | 40 | 1/1/1 |
| Town10HD/sparse_b1 | PASS_CORE | 560 | 15.0 | 81.5 | 12.5 | 12.1 | 0.74 | 852 | 375 | 212 | 298.1 | 6 | 15 | 1/1/1 |
| Town10HD/sparse_r30 | INVALID_RECORDING | 560 | 15.0 | 107.4 | 5.8 | 21.1 | 0.07 | 453 | 0 | 0 | 3078.0 | 0 | 14 | 0/0/0 |
| Town10HD/sparse_r60 | INVALID_RECORDING | 560 | 15.0 | 155.4 | 6.7 | 53.5 | 0.0 | 278 | 0 | 0 | 769.5 | 0 | 15 | 0/0/0 |
| Town10HD/sparse_r90 | PASS_CORE | 560 | 15.0 | 94.2 | 18.7 | 18.0 | 0.88 | 508 | 487 | 339 | 564.1 | 17 | 15 | 1/1/1 |

## INVALID_RECORDING runs (must exclude / re-record)
- **Town01__dynamic_v3__runsparse_b1**: matched=0, 96.5% objects >150m, in-FOV<50m=0.0/f
- **Town01__dynamic_v3__runsparse_r30**: matched=1, 96.3% objects >150m, in-FOV<50m=0.0/f
- **Town01__dynamic_v3__runsparse_r90**: matched=0, 100.0% objects >150m, in-FOV<50m=0.0/f
- **Town06__dynamic_v3__rundense_r30**: 95.0% objects >150m
- **Town06__dynamic_v3__rundense_r60**: 97.5% objects >150m
- **Town06__dynamic_v3__rundense_r90**: matched=0, 98.8% objects >150m, in-FOV<50m=0.0/f
- **Town06__dynamic_v3__runmedium_r60**: matched=0, 100.0% objects >150m, in-FOV<50m=0.0/f
- **Town06__dynamic_v3__runmedium_r90**: matched=0, 100.0% objects >150m, in-FOV<50m=0.0/f
- **Town06__dynamic_v3__runsparse_r30**: YOLO det=0, matched=0, 98.7% objects >150m, in-FOV<50m=0.0/f
- **Town06__dynamic_v3__runsparse_r60**: matched=0, 100.0% objects >150m, in-FOV<50m=0.0/f
- **Town06__dynamic_v3__runsparse_r90**: matched=0, 100.0% objects >150m, in-FOV<50m=0.0/f
- **Town07__dynamic_v3__rundense_b1**: SPAWN-COLLISION: 56% dets fill >50% frame
- **Town07__dynamic_v3__runsparse_r30**: in-FOV<50m=0.03/f
- **Town07__dynamic_v3__runsparse_r60**: matched=2, in-FOV<50m=0.0/f
- **Town10HD__dynamic_v3__runmedium_r60**: matched=0, in-FOV<50m=0.0/f
- **Town10HD__dynamic_v3__runsparse_r30**: matched=0
- **Town10HD__dynamic_v3__runsparse_r60**: matched=0, in-FOV<50m=0.0/f

## Core set: 25 runs | Low-yield: 6 | Invalid: 17
- rotated-spawn (r30/r60/r90) low-yield/invalid rate: 53% vs b1(spawn=0): 33%

## Verdict
- Town06 sparse_r30 status: **INVALID_RECORDING** (previously hidden by a header-only placeholder — now correctly classified).
- Only PASS_CORE runs may enter core experiments; LOW_YIELD -> appendix/robustness; INVALID -> excluded/re-record.
- See PAPER2_CARLA_SPAWN_BUG_AUDIT.md for root cause of the far-object / low-yield pattern.
