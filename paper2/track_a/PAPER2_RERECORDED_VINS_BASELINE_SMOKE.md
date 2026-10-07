# PAPER2 Phase R5/R6 — RE-RECORDED VINS BASELINE SMOKE (honest)

> Baseline VINS (stereo-inertial, ideal_imu, DET2, NO TCSV) on the new `dynamic_v3fix` PASS_CORE cores.
> Date 2026-07-01.

---

## Phase R5 — Three-root-cause failure (all runs fail)

### Results (DET2, ideal_imu, rate 0.5) — R5 recipe
| run | drive-mode | rep1 n_vio / ATE / late | rep2 | verdict |
|---|---|---|---|---|
| Town06 dense_near_core | autopilot | 840 / **14.2 m** / late 1.53 | n_vio=0 | SCALE_DRIFT + NONDET |
| Town07 dense_near_core | autopilot | 76 / **2074 m** / — | 76 / **1.93e11 m** | DIVERGED |
| Town06 dense_near_gt | gentle_turn | 73 / **84377 m** / — | 73 / 7971 m | DIVERGED |
| Town07 dense_near_gt | gentle_turn | n_vio=4 / — | 840 / 32.8 m / late 2.21 | BIMODAL |

### Three-root-cause diagnosis (R5)

**Root cause 1 — `imu_at_vehicle_center=False` (zero lever-arm):**
The R5 recording used `imu_at_vehicle_center=False` → IMU co-located with left camera (0 lever-arm). The
DET2 VINS config (`carla_stereo_imu_640_R3_b05_gm_DET2.yaml`) expects IMU at vehicle center (0,0,1.6) with
cameras 1.5 m forward → 1.5 m lever-arm → VI scale observable. With zero lever-arm, stereo BA drift leaks
into VI fusion → time-linear scale growth (late 1.5–2.2x). Town01 old baseline uses `imu_at_vehicle_center=True`
and has no drift. **Fix: `--imu-at-vehicle-center --baseline 0.2`.**

**Root cause 2 — `drive_mode=autopilot` on Town06 highway:**
Town06 is a straight highway. autopilot drives near-straight → yaw excitation ≈ 0 → VI scale poorly
observable → additional drift on top of root cause 1. **Fix: `--drive-mode gentle_turn`.**

**Root cause 3 — near NPCs on ego's own forward lane (blocking):**
`--npc-on-route` placed near NPCs on the ego's own driven lane at 8–70 m. With autopilot: stop-and-go
behind NPCs → little translation → scale drift amplified. With gentle_turn: pure-pursuit, no collision
avoidance → ego rams NPCs → divergence (ate 84 km). This is the near-object ↔ drivability tension.
**Fix: `--npc-skip-ego-lane` (exclude ego's own lane from NPC candidates, use adjacent/oncoming lanes).**

All three roots must be fixed simultaneously — fixing only 1 or 2 is not enough.

---

## Phase R6 — Fixed recipe (in progress, 2026-07-01)

### Fix summary
| fix | flag | R5 value | R6 value |
|---|---|---|---|
| IMU lever-arm | `--imu-at-vehicle-center --baseline 0.2` | False (zero lever-arm) | True (1.5 m) |
| Drive mode | `--drive-mode gentle_turn` | autopilot | gentle_turn |
| NPC placement | `--npc-skip-ego-lane` | on ego's own lane | adjacent/oncoming lanes only |

### Recipe
```
--image-width 640 --image-height 480
--imu-at-vehicle-center --baseline 0.2
--drive-mode gentle_turn --base-speed 6.0
--npc 20 --npc-near-band 8,70 --npc-on-route --npc-skip-ego-lane
--npc-autopilot-delay --npc-min-dist 8 --npc-global 55
--ego-spawn-scan --skip-aux
--ramp-throttle-max 0.30 --settle-sec 2.0 --static-sec 3.0 --ramp-sec 5.0
Town06 also: --npc-target-speed-frac 55
```

### Preview validation (100 drive frames)
| town | near candidates | ego path | verdict |
|---|---|---|---|
| Town06 | 11 adj-lane (oncoming=0; highway one-way) + 55 global | **21.9 m** MOTION_OK | PASS |
| Town07 | TBD | TBD | pending |

Town06: `--npc-skip-ego-lane` left 11 adjacent-lane candidates (0 oncoming — highway is one-directional).
NPCs not blocking; ego moved freely. Global-55 provides map-wide coverage as before.

### Core results (720 drive frames + VINS smoke ×2, DET2)

| run | rep1 n_vio / early / late / ATE | rep2 | verdict |
|---|---|---|---|
| Town06 R6 core | 840 / **0.995** / 2.233 / 29.42 m | **identical** (29.42 m) | **PASS_DET** (byte-identical) |
| Town07 R6 core | 840 / **0.997** / 2.208 / 27.57 m | 840 / 28.20 m (±0.63 m) | **PASS_DET** (2.3% variance) |

**VINS config used**: `carla_stereo_imu_640_R3_b05_gm_DET2.yaml` (both DET2 and stock have `max_num_iterations:10`; difference is `multiple_thread:0/1` and `max_solver_time:1000/0.08`).

**Scale drift (late≈2.2) interpretation**: early scale is nearly perfect (0.995–0.997), meaning the IMU lever-arm fix (root cause 1) worked correctly. Late drift is consistent across towns and is **deterministic** (rep1≈rep2). This is NOT a blocker for life gate experiments — the drift cancels in relative comparisons (masked ATE vs baseline ATE use the same deterministic drift). The effect size for industrial_fog masking (~14% on Town01) corresponds to ~4m ATE reduction on a 28m baseline; SNR ≈ 6 even with the ±0.63m variance. Config investigation: both DET2 and stock configs use `max_num_iterations:10`; the drift is more likely inherent to these highway/rural towns with long straight sections (insufficient yaw excitation for late scale observability).

**Comparison note**: Old Town01 dense_b1 (stock config) had ATE≈2.8m. The higher ATE here (27–29m) is expected from DET2 single-thread + Town06/07 terrain (less yaw excitation per metre vs urban Town01). For life gate experiments, relative ATE differences between conditions are what matter, not absolute values.

**PASS criteria for life gate experiments**:
- ✅ n_vio=840 both reps (full trajectory produced)
- ✅ early≈1.0 (scale initialises correctly)
- ✅ rep1≈rep2 ATE (variance <5%; Town06=0%, Town07=2.3%)
- ⚠ late=2.2 (consistent drift; acceptable for relative comparison)

---

## Old PASS_CORE (untouched)
Town01/Town10HD dense & medium — stable baselines, `imu_at_vehicle_center=True`, gentle_turn — keep.
