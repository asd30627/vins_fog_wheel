# PAPER2_RAW_OBJECT_BENCHMARK — Workstream B / Phase G1

> 24 dynamic_v3 runs, 20921 detections, 15811 GT-matched. SGBM real depth. G1 benchmark.

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
| 0-15m | 1863 | 1.93 | 3.84 | 1.64 | 5.7 |
| 15-30m | 4164 | 2.12 | 24.55 | 3.17 | 17.2 |
| 30m+ | 9784 | 7.79 | 132.38 | 7.98 | 65.6 |

## By density × distance bin
| density | bin | n | pos_med | pos_p95 | spd_med | dir_med |
|---|---|---|---|---|---|---|
| sparse | 0-15m | 153 | 1.64 | 3.04 | 2.33 | 22.3 |
| sparse | 15-30m | 362 | 2.21 | 16.63 | 4.97 | 24.3 |
| sparse | 30m+ | 1233 | 6.38 | 58.90 | 22.10 | 67.8 |
| medium | 0-15m | 733 | 1.99 | 3.05 | 1.67 | 3.7 |
| medium | 15-30m | 1406 | 2.05 | 7.91 | 3.43 | 11.9 |
| medium | 30m+ | 2792 | 6.06 | 116.84 | 7.59 | 61.5 |
| dense | 0-15m | 977 | 1.88 | 14.16 | 1.48 | 7.2 |
| dense | 15-30m | 2396 | 2.18 | 52.32 | 2.92 | 19.0 |
| dense | 30m+ | 5759 | 10.91 | 141.88 | 7.60 | 68.3 |

## By town × distance bin
| town | bin | n | pos_med | pos_p95 | spd_med | dir_med |
|---|---|---|---|---|---|---|
| Town01 | 0-15m | 1172 | 1.94 | 3.16 | 1.80 | 4.8 |
| Town01 | 15-30m | 2134 | 2.07 | 8.01 | 3.08 | 15.5 |
| Town01 | 30m+ | 3717 | 5.75 | 112.52 | 7.90 | 48.8 |
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
