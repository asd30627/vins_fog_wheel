# PAPER2_THRESHOLD_ROBUSTNESS_REGROUPED

> Robustness under the corrected CARLA `(town,run,track_id)` grouping. (A) C1 phenomenon across 3×3 thresholds per dataset; (B) TCSV-vs-distance verdict across vel_t (in-domain).

## A. C1 phenomenon robustness (per dataset, pos_t × vel_t)
| dataset | combos | R1&R2&R3&R4 pass | vel_valid@0-15 range | vel_valid@30m+ range |
|---|---|---|---|---|
| CARLA | 9 | **8/9** | [0.19,0.33] | [0.03,0.10] |
| KITTI | 9 | **6/9** | [0.52,0.75] | [0.13,0.29] |

- Overall C1 checks pass **14/18** threshold combos (corrected grouping).
- Note: C1 is computed from pos/vel error by distance bin and does NOT depend on temporal grouping; the grouping fix affects MODEL features (§B), not the phenomenon.

## B. TCSV-HistGBM vs distance gate across velocity threshold (in-domain, corrected grouping)
| dataset | vel_t | TCSV AUROC | TCSV AURC↓ | distance AURC↓ | TCSV beats? |
|---|---|---|---|---|---|
| CARLA | 2.0 | 0.812 | 0.746 | 0.809 | ✅ |
| CARLA | 3.0 | 0.819 | 0.694 | 0.773 | ✅ |
| CARLA | 5.0 | 0.782 | 0.641 | 0.725 | ✅ |
| KITTI | 2.0 | 0.915 | 0.318 | 0.563 | ✅ |
| KITTI | 3.0 | 0.934 | 0.205 | 0.457 | ✅ |
| KITTI | 5.0 | 0.950 | 0.107 | 0.341 | ✅ |

- TCSV beats distance gate (AURC↓) in **6/6** threshold settings.
- Honest: in-domain CARLA margins are small (velocity intrinsically hard); KITTI margins large. Cross-dataset robustness is reported separately in PAPER2_PUBLIC_PROXY_BASELINE_RESULTS.md.
