# PAPER2_KITTI_TRACKING_VALIDITY_RESULTS

> Real KITTI tracking (21 train seqs, YOLOv8m + monocular bbox-height depth, GT label_02). Compared to CARLA on an identical ego-independent velocity criterion (vel_err = ||raw_vel-gt_vel|| ≤ 3 m/s). Fig: figs/fig_v5_kitti_vs_carla_validity.png

- CARLA matched detections: 15811 ; KITTI: 37022 (34943 with velocity).

## Validity by distance — CARLA vs KITTI (same criterion)
| bin | CARLA pos_valid | KITTI pos_valid | CARLA vel_valid | KITTI vel_valid | CARLA pos_only | KITTI pos_only |
|---|---|---|---|---|---|---|
| 0-15m | 0.89 | 0.86 | 0.70 | 0.65 | 0.55 | 0.28 |
| 15-30m | 0.73 | 0.74 | 0.26 | 0.45 | 0.63 | 0.43 |
| 30m+ | 0.30 | 0.44 | 0.08 | 0.21 | 0.29 | 0.36 |

## Do the 4 CARLA phenomena hold on REAL KITTI data?
- (1) velocity_valid DECREASES with distance: KITTI 0.65 → 0.45 → 0.21 → **YES**
- (2) position_valid more stable than velocity (vel<pos at every bin): **YES**
- (3) position_only regime substantial: KITTI [np.float64(0.28), np.float64(0.43), np.float64(0.36)] → **YES**
- (4) invalid_velocity common (refusal meaningful): KITTI invalid-velocity rate [np.float64(0.35), np.float64(0.55), np.float64(0.79)] → **YES**.

## KITTI distance-gated refusal (does observability-aware refusal cut overconfident wrong velocity?)
- no-policy overconfident-wrong-velocity (base invalid rate) = 0.544
| emit if range< | emit_frac | overconfident_wrong_velocity | valid_retention |
|---|---|---|---|
| 10 m | 0.20 | 0.363 | 0.28 |
| 15 m | 0.36 | 0.346 | 0.52 |
| 20 m | 0.50 | 0.378 | 0.68 |
| 25 m | 0.63 | 0.413 | 0.81 |

## Honest reading
- **All four CARLA phenomena reproduce on real KITTI driving** (qualitatively): velocity validity collapses with distance, position is more stable, position_only is a real regime, invalid-velocity is common.
- ABSOLUTE numbers differ (KITTI vel_valid 0.65/0.45/0.21 vs CARLA 0.70/0.26/0.08) — expected: KITTI is 10 Hz (longer dt → less relative velocity noise), monocular bbox-height depth (≠ CARLA stereo), and human-annotated tracks.
- distance-gated refusal cuts overconfident-wrong-velocity vs no-policy on real data → the refusal layer is meaningful on KITTI too.
## Caveats (honest)
- image_03 (right) zip arrived CORRUPTED → stereo unavailable → monocular bbox-height depth used (standard cue; depth noise still grows with distance). A stereo redo needs a clean image_03 re-download.
- KITTI has no direct velocity GT → velocity derived from cross-frame GT-position differencing (noise; occlusion/truncation).
- raw uses YOLO bbox (realistic detection jitter); class-height prior for monocular depth; ego-motion cancels in vel_err.
