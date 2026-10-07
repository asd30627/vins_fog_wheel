# PAPER2_PHASE_MAP_V0 — Workstream B (phase map)

> Raw object reliability phase map (G0/G1). cells = pos_err median (m) / matched n. Localization-quality axis (yaw injection) is the per-detection yaw1°_lat = r·sin(1°) lever; here we map the OBJECT-condition axes (density × distance) on nominal ego pose.

## pos_err median (m) — density × distance
| density \ bin | 0-15m | 15-30m | 30m+ |
|---|---|---|---|
| sparse | 1.47 (n=225) | 2.32 (n=474) | 11.32 (n=2675) |
| medium | 1.97 (n=909) | 2.07 (n=1766) | 14.54 (n=4726) |
| dense | 1.90 (n=1184) | 2.40 (n=3042) | 11.74 (n=8566) |

## speed_err median (m/s) — density × distance
| density \ bin | 0-15m | 15-30m | 30m+ |
|---|---|---|---|
| sparse | 1.86 (n=225) | 4.80 (n=474) | 18.23 (n=2675) |
| medium | 1.56 (n=909) | 3.62 (n=1766) | 8.03 (n=4726) |
| dense | 1.42 (n=1184) | 3.05 (n=3042) | 8.83 (n=8566) |

## Reading
- position error grows with distance bin (raw stereo-depth quantization).
- speed error explodes in 30m+ (depth-jitter) -> far objects = high-uncertainty/invalid regime for NOUE.
- yaw lever (e_lat≈r·sin Δψ) is the localization-quality coupling, quantified per-detection in benchmark_all.csv.
- cells with n<10 are low-confidence.
