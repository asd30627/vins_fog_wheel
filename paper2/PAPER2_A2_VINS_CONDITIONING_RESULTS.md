# PAPER2_A2_VINS_CONDITIONING_RESULTS (run 20260630_124331)

> The make-or-break test: does VINS-quality conditioning improve object-state reliability?
> vins-matched rows=15066 (train 10719/val 1954/test 2393); degraded frac 0.807.
> Models on identical vins-matched samples. A2 looks at the **degraded-localization stratum** (vins_outlier>0.5 OR vins_feat<50).

## A2 VERDICT: **FAILED/INCONCLUSIVE**
- degraded-bin with-VINS vs no-VINS: NLL_better=False, AUROC_better=False, riskcov_better=False
- overall with-VINS vs no-VINS: NLL_better=False, AUROC_better=False
- rule: promising = with-VINS wins >=2/3 degraded metrics; weak = wins overall only; else failed/inconclusive.

### Overall (test)
| model | n | NLL | ANEES | ECE | AUROC | riskcov@80 | overconf |
|---|---|---|---|---|---|---|---|
| distance_only | 2393 | 5.256 | 1.28 | 0.121 | 0.449 | 16.81 | 0.384 |
| geometry_gate | 2393 | 582.348 | 1160.09 | 0.111 | 0.548 | 22.17 | 0.490 |
| noue_no_vins | 2393 | 62.424 | 119.31 | 0.078 | 0.555 | 18.02 | 0.438 |
| noue_with_vins | 2393 | 126.870 | 248.43 | 0.065 | 0.484 | 22.48 | 0.544 |

### Degraded-localization stratum (the A2 core)
| model | n | NLL | ANEES | ECE | AUROC | riskcov@80 | overconf |
|---|---|---|---|---|---|---|---|
| distance_only | 1687 | 5.534 | 1.74 | 0.109 | 0.468 | 28.10 | 0.277 |
| geometry_gate | 1687 | 797.587 | 1590.90 | 0.120 | 0.527 | 27.42 | 0.494 |
| noue_no_vins | 1687 | 83.927 | 162.41 | 0.101 | 0.561 | 23.12 | 0.394 |
| noue_with_vins | 1687 | 177.312 | 349.87 | 0.090 | 0.540 | 25.83 | 0.446 |

### High-error objects (pos_err>3m)
| model | n | NLL | ANEES | ECE | AUROC | riskcov@80 | overconf |
|---|---|---|---|---|---|---|---|
| distance_only | 781 | 6.507 | 3.92 | 0.206 | nan | 46.17 | 0.384 |
| geometry_gate | 781 | 1779.458 | 3554.13 | 0.376 | nan | 66.91 | 0.498 |
| noue_no_vins | 781 | 185.314 | 364.88 | 0.341 | nan | 51.44 | 0.499 |
| noue_with_vins | 781 | 382.754 | 760.26 | 0.376 | nan | 60.92 | 0.499 |

## Per distance bin (with-VINS vs no-VINS, NLL)
| bin | no-VINS NLL | with-VINS NLL | no-VINS AUROC | with-VINS AUROC |
|---|---|---|---|---|
| 0-15m | 103.391 | 185.414 | 0.533 | 0.517 |
| 15-30m | 55.508 | 103.884 | 0.465 | 0.292 |
| 30m+ | 9.588 | 72.185 | 0.674 | 0.617 |

## Per town (NLL no-VINS -> with-VINS)
- Town01: 62.424 -> 126.870

## Honest caveats
- object errors use GT ego-comp -> VINS quality acts as a SCENE-DIFFICULTY proxy (not direct VINS-error propagation).
- with-VINS has more features; the A2 claim rests on DEGRADED-bin gain, not raw overall gain.
- ANEES far from 1 = miscalibrated scale (heavy 30m+ tail); report log-space too in future.
- single daytime run; group-split by run; verdict is a signal, not a final paper claim.


---

# A2 TEST 2 — VINS-error-PROPAGATED object WORLD error (deployment mechanism)

> object_world_err = sensor body_pos_err + ego loc drift (sim3-aligned) + |yaw drift|*range. n=15066 (train 10719/test 2393). This is the mechanism test 1 could not see (test 1 used GT ego-comp).

## A2 (world-frame) VERDICT: **WEAK**
- degraded: with-VINS vs no-VINS NLL_better=False AUROC_better=True riskcov_better=False
- overall: NLL_better=False AUROC_better=True
- world_err median 53.33 m vs sensor-only 3.08 m (localization adds 50.25 m median).

### Overall (test)
| model | n | NLL | ANEES | ECE | AUROC | riskcov@80 | overconf |
|---|---|---|---|---|---|---|---|
| no_vins | 2393 | 21.492 | 34.37 | 0.143 | 0.586 | 82.62 | 0.422 |
| with_vins | 2393 | 32.277 | 56.51 | 0.230 | 0.586 | 91.80 | 0.462 |

### Degraded-localization stratum
| model | n | NLL | ANEES | ECE | AUROC | riskcov@80 | overconf |
|---|---|---|---|---|---|---|---|
| no_vins | 1687 | 18.244 | 27.83 | 0.162 | 0.591 | 83.51 | 0.431 |
| with_vins | 1687 | 33.847 | 59.87 | 0.231 | 0.614 | 91.31 | 0.405 |

## Per distance bin (NLL no-VINS -> with-VINS)
- 0-15m: 4.566 -> 4.528 ; AUROC 0.584 -> 0.644
- 15-30m: 5.521 -> 7.594 ; AUROC 0.760 -> 0.728
- 30m+: 48.197 -> 74.522 ; AUROC 0.704 -> 0.666

## Honest caveats (test 2)
- world_err uses an ANALYTICAL additive propagation model (sensor + loc drift + yaw*range), not a re-localized object pipeline.
- VINS scale drift here is partly artifact of aggressive-turn 640 recordings; real VINS would drift less.
- if with-VINS wins, it confirms VINS quality conditions the LOCALIZATION-propagated object error (the deployment claim);
  it does NOT revive test-1 (sensor-only error), which VINS quality cannot help.
