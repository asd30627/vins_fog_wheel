# PAPER2 Part 0 — PER-DET REBUILD AUDIT

> 4-town CARLA validity dataset rebuilt from 48 per-det CSVs. Grouping = (town, run, track_id) [CARLA], (seq, track_id) [KITTI] — confirmed, NOT the old bug. All features runtime-observable; only LABELS use GT. Date 2026-07-01.

## 0. Per-det CSV integrity
- per-det CSV files: **48** (target 48 = 24 prior [Town01,Town10HD] + 24 new [Town06,Town07])
- readable: **48/48**; all source recordings = 720 stereo frames (verified).
- detection rows/run: min=3 median=545 max=2273 (b1/spawn=0 rich; rotated-spawn low-yield).
- low-yield runs (<200 det rows; mostly rotated-spawn r30/r60/r90, objects out of detectable range — EXPECTED): **13**.
- genuinely-empty runs (0 detections): **1** -> Town06__dynamic_v3__runsparse_r30 (Town06 sparse_r30: 26 GT objs/frame but all >160 m → YOLO det=0 at 640×480; header-only marker kept).
- truncation bugs after fix: **0** (the sparse_b1 --max-frames-50 test artifact was recomputed full).

## 1. CARLA dataset totals
- total GT-matched detections (pos_err present): **23567**
- towns: ['Town01', 'Town06', 'Town07', 'Town10HD']  | runs: 12 (per town) | tracks: **539**
- has velocity estimate (has_v=1): **15215** (64.6%)

## 2. Label distribution (velocity criterion = ego-independent vel_err<=3 m/s; pos<=3 m)
| label | rate |
|---|---|
| velocity_valid | 0.1070 |
| position_valid | 0.4054 |
| full_state_valid (pos AND vel) | 0.0656 |
| position_only (pos AND NOT vel) | 0.3399 |
| invalid (NOT vel) | 0.8930 |

## 3. By town
| town | n | runs | tracks | vel_valid | pos_valid | has_v |
|---|---|---|---|---|---|---|
| Town01 | 7023 | 10 | 134 | 0.1132 | 0.5808 | 0.484 |
| Town06 | 4173 | 6 | 89 | 0.1004 | 0.1356 | 0.9355 |
| Town07 | 3583 | 12 | 91 | 0.0915 | 0.3676 | 0.4996 |
| Town10HD | 8788 | 9 | 225 | 0.1114 | 0.4089 | 0.6966 |

## 4. By distance bin
| bin | n | vel_valid | pos_valid | full_state | position_only |
|---|---|---|---|---|---|
| 0-15m | 4676 | 0.259 | 0.522 | 0.1946 | 0.3274 |
| 15-30m | 6149 | 0.1199 | 0.5448 | 0.068 | 0.4768 |
| 30m+ | 12742 | 0.045 | 0.2954 | 0.017 | 0.2784 |

## 5. Per-run (first 12 rows; full in paper2_perdet_audit_per_run.csv)
| town | run | n | tracks | vel_valid | pos_valid |
|---|---|---|---|---|---|
| Town01 | dense_b1 | 1180 | 31 | 0.1407 | 0.678 |
| Town01 | dense_r30 | 872 | 13 | 0.094 | 0.4771 |
| Town01 | dense_r60 | 1002 | 13 | 0.0938 | 0.6377 |
| Town01 | dense_r90 | 482 | 19 | 0.1784 | 0.1846 |
| Town01 | medium_b1 | 1006 | 17 | 0.0557 | 0.6511 |
| Town01 | medium_r30 | 675 | 6 | 0.3141 | 0.9378 |
| Town01 | medium_r60 | 569 | 13 | 0.109 | 0.5062 |
| Town01 | medium_r90 | 351 | 3 | 0.0513 | 0.5584 |
| Town01 | sparse_r30 | 1 | 1 | 0.0 | 0.0 |
| Town01 | sparse_r60 | 885 | 18 | 0.0215 | 0.4102 |
| Town06 | dense_b1 | 841 | 25 | 0.1023 | 0.1332 |
| Town06 | dense_r30 | 450 | 14 | 0.1022 | 0.2311 |

## 6. KITTI (reference real dataset)
- loaded OK: n=37022, seqs=21, vel_valid=0.4300, pos_valid=0.6979

## 7. Verdict
- 4-town rebuild **COMPLETE & CLEAN** (48/48 readable; 0 truncation bugs; 13 expected low-yield rotated-spawn runs).
- grouping (town,run,track_id) confirmed in loader; no track spans train/test.
- 4 towns (Town01, Town06, Town07, Town10HD) ⇒ more group diversity for CARLA in-domain split.
- velocity base rate imbalanced (minority=valid) -> use AURC/selective metrics, not accuracy.
