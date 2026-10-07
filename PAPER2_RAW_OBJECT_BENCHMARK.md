# PAPER2_RAW_OBJECT_BENCHMARK — Workstream B / Phase G1

> 48 dynamic_v3 runs, 30102 detections, 23567 GT-matched. SGBM real depth. G1 benchmark.

## Per-run
| run | det | matched |
|---|---:|---:|
| Town01__dynamic_v3__rundense_b1 | 1291 | 1180 |
| Town01__dynamic_v3__rundense_r30 | 1143 | 872 |
| Town01__dynamic_v3__rundense_r60 | 1293 | 1002 |
| Town01__dynamic_v3__rundense_r90 | 565 | 482 |
| Town01__dynamic_v3__runmedium_b1 | 1094 | 1006 |
| Town01__dynamic_v3__runmedium_r30 | 706 | 675 |
| Town01__dynamic_v3__runmedium_r60 | 661 | 569 |
| Town01__dynamic_v3__runmedium_r90 | 364 | 351 |
| Town01__dynamic_v3__runsparse_b1 | 6 | 0 |
| Town01__dynamic_v3__runsparse_r30 | 5 | 1 |
| Town01__dynamic_v3__runsparse_r60 | 1025 | 885 |
| Town01__dynamic_v3__runsparse_r90 | 5 | 0 |
| Town06__dynamic_v3__rundense_b1 | 856 | 841 |
| Town06__dynamic_v3__rundense_r30 | 541 | 450 |
| Town06__dynamic_v3__rundense_r60 | 327 | 272 |
| Town06__dynamic_v3__rundense_r90 | 3 | 0 |
| Town06__dynamic_v3__runmedium_b1 | 881 | 861 |
| Town06__dynamic_v3__runmedium_r30 | 727 | 511 |
| Town06__dynamic_v3__runmedium_r60 | 7 | 0 |
| Town06__dynamic_v3__runmedium_r90 | 3 | 0 |
| Town06__dynamic_v3__runsparse_b1 | 1270 | 1238 |
| Town06__dynamic_v3__runsparse_r30 | 0 | 0 |
| Town06__dynamic_v3__runsparse_r60 | 6 | 0 |
| Town06__dynamic_v3__runsparse_r90 | 6 | 0 |
| Town07__dynamic_v3__rundense_b1 | 864 | 475 |
| Town07__dynamic_v3__rundense_r30 | 6 | 6 |
| Town07__dynamic_v3__rundense_r60 | 844 | 766 |
| Town07__dynamic_v3__rundense_r90 | 935 | 850 |
| Town07__dynamic_v3__runmedium_b1 | 349 | 312 |
| Town07__dynamic_v3__runmedium_r30 | 44 | 42 |
| Town07__dynamic_v3__runmedium_r60 | 338 | 297 |
| Town07__dynamic_v3__runmedium_r90 | 545 | 447 |
| Town07__dynamic_v3__runsparse_b1 | 195 | 74 |
| Town07__dynamic_v3__runsparse_r30 | 20 | 17 |
| Town07__dynamic_v3__runsparse_r60 | 5 | 2 |
| Town07__dynamic_v3__runsparse_r90 | 409 | 295 |
| Town10HD__dynamic_v3__rundense_b1 | 2273 | 2017 |
| Town10HD__dynamic_v3__rundense_r30 | 2126 | 1562 |
| Town10HD__dynamic_v3__rundense_r60 | 702 | 407 |
| Town10HD__dynamic_v3__rundense_r90 | 1834 | 1610 |
| Town10HD__dynamic_v3__runmedium_b1 | 1081 | 507 |
| Town10HD__dynamic_v3__runmedium_r30 | 1298 | 862 |
| Town10HD__dynamic_v3__runmedium_r60 | 272 | 0 |
| Town10HD__dynamic_v3__runmedium_r90 | 1086 | 961 |
| Town10HD__dynamic_v3__runsparse_b1 | 852 | 375 |
| Town10HD__dynamic_v3__runsparse_r30 | 453 | 0 |
| Town10HD__dynamic_v3__runsparse_r60 | 278 | 0 |
| Town10HD__dynamic_v3__runsparse_r90 | 508 | 487 |

## By distance bin (matched)
| bin | n | pos_med | pos_p95 | spd_med | dir_med |
|---|---|---|---|---|---|
| 0-15m | 2318 | 1.90 | 4.88 | 1.53 | 6.7 |
| 15-30m | 5282 | 2.25 | 20.80 | 3.37 | 15.5 |
| 30m+ | 15967 | 12.39 | 163.01 | 9.68 | 51.9 |

## By density × distance bin
| density | bin | n | pos_med | pos_p95 | spd_med | dir_med |
|---|---|---|---|---|---|---|
| sparse | 0-15m | 225 | 1.47 | 2.99 | 1.86 | 11.7 |
| sparse | 15-30m | 474 | 2.32 | 17.84 | 4.80 | 23.7 |
| sparse | 30m+ | 2675 | 11.32 | 184.20 | 18.23 | 32.3 |
| medium | 0-15m | 909 | 1.97 | 3.16 | 1.56 | 4.8 |
| medium | 15-30m | 1766 | 2.07 | 8.71 | 3.62 | 11.2 |
| medium | 30m+ | 4726 | 14.54 | 219.34 | 8.03 | 46.8 |
| dense | 0-15m | 1184 | 1.90 | 13.79 | 1.42 | 7.6 |
| dense | 15-30m | 3042 | 2.40 | 33.21 | 3.05 | 16.4 |
| dense | 30m+ | 8566 | 11.74 | 149.49 | 8.83 | 60.4 |

## By town × distance bin
| town | bin | n | pos_med | pos_p95 | spd_med | dir_med |
|---|---|---|---|---|---|---|
| Town01 | 0-15m | 1172 | 1.94 | 3.16 | 1.80 | 4.8 |
| Town01 | 15-30m | 2134 | 2.07 | 8.01 | 3.08 | 15.5 |
| Town01 | 30m+ | 3717 | 5.75 | 112.52 | 7.90 | 48.8 |
| Town06 | 0-15m | 87 | 1.74 | 35.29 | 2.72 | 20.9 |
| Town06 | 15-30m | 539 | 3.18 | 19.04 | 4.38 | 13.8 |
| Town06 | 30m+ | 3547 | 19.27 | 240.92 | 20.26 | 16.0 |
| Town07 | 0-15m | 368 | 1.65 | 4.83 | 1.01 | 7.9 |
| Town07 | 15-30m | 579 | 2.44 | 12.41 | 3.83 | 7.4 |
| Town07 | 30m+ | 2636 | 9.63 | 183.77 | 8.84 | 73.1 |
| Town10HD | 0-15m | 691 | 1.90 | 14.59 | 1.36 | 7.0 |
| Town10HD | 15-30m | 2030 | 2.22 | 53.38 | 3.24 | 18.1 |
| Town10HD | 30m+ | 6067 | 9.66 | 138.23 | 8.00 | 70.0 |

## Insufficient-sample bins
- overall bins with n<10: none
- per (density,bin) insufficient: []

## Notes
- match = bearing 4° to front GT actor; pos_err = body-frame (fwd,lat) distance.
- velocity at far range dominated by depth-jitter (expect large speed_err in 30m+).
- G1 benchmark; not a tuned final result.
