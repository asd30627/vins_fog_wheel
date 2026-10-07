# PAPER2_PHASE_MAP_V0 — Workstream B (phase map)

> Raw object reliability phase map (G0/G1). cells = pos_err median (m) / matched n. Localization-quality axis (yaw injection) is the per-detection yaw1°_lat = r·sin(1°) lever; here we map the OBJECT-condition axes (density × distance) on nominal ego pose.

## pos_err median (m) — density × distance
| density \ bin | 0-15m | 15-30m | 30m+ |
|---|---|---|---|
| sparse | 1.64 (n=153) | 2.21 (n=362) | 6.38 (n=1233) |
| medium | 1.99 (n=733) | 2.05 (n=1406) | 6.06 (n=2792) |
| dense | 1.88 (n=977) | 2.18 (n=2396) | 10.91 (n=5759) |

## speed_err median (m/s) — density × distance
| density \ bin | 0-15m | 15-30m | 30m+ |
|---|---|---|---|
| sparse | 2.33 (n=153) | 4.97 (n=362) | 22.10 (n=1233) |
| medium | 1.67 (n=733) | 3.43 (n=1406) | 7.59 (n=2792) |
| dense | 1.48 (n=977) | 2.92 (n=2396) | 7.60 (n=5759) |

## Reading
- position error grows with distance bin (raw stereo-depth quantization).
- speed error explodes in 30m+ (depth-jitter) -> far objects = high-uncertainty/invalid regime for NOUE.
- yaw lever (e_lat≈r·sin Δψ) is the localization-quality coupling, quantified per-detection in benchmark_all.csv.
- cells with n<10 are low-confidence.
