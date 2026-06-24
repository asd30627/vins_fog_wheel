# RELATED_WORK_DIFF — competitor comparison (for the paper's Related Work + reviewer rebuttals)

> Strategy (user-directed, legitimate): **borrow + cite methods heavily (inherit their validation); place novelty on the dimensions they did not touch; package the story in the problem setting.** The only thing we never do is pretend a borrowed method is our own invention. Every method below is cited explicitly in the paper body, stating "we extend it to the dimension it did not cover" — no method is claimed as original.

## Competitor comparison table

| Method | Uses vision? | Where the AI acts | Cross-FOG-grade? | Dynamic scene? | Sensor | Our difference |
|---|---|---|---|---|---|---|
| FoGNet (Zhao et al.) | ❌ | front-end FOG de-noising | ❌ single grade | ❌ clean | FOG 0.05 | fusion-layer arbitration / has vision / cross-grade / dynamic |
| DualProNet (Solodar & Klein) | ✅ | IMU process-noise cov | ❌ single | partial | MEMS | rotation arbitration (not process noise) / cross-FOG-grade |
| GyroNet / AirIMU / TLIO / Brossard / Buchanan | ❌ / partial | inertial de-noising / bias | ❌ single | ❌ | MEMS | navigation-grade FOG / cross-grade / fusion-layer |
| Visual-Selective-VIO | ✅ | policy network toggles vision on/off | ❌ | ❌ | MEMS | continuous arbitration (not binary) / FOG-grade dimension |
| Advanced Navigation (commercial) | – | proprietary NN | ❌ | – | FOG+GNSS | no-GPS / publicly reproducible / academic |

## Moat (structurally impossible for others)

Three FOG-grade assets: CARLA tunable + KAIST industrial-grade + a physical top-grade FOG (0.03°/hr). Without cross-grade FOG hardware, the grade-dimension study cannot be done.

## Citation discipline

Every method above is cited in the paper body, explicitly stated as "extended to the dimension it did not address", never presented as an original method.

## Per-knife defence (pre-submission self-review)

- **Knife 1 — "how is this different from DualProNet / FoGNet?"** → the comparison table + the three-point difference (fusion-layer / cross-grade / dynamic).
- **Knife 2 — "is the CARLA simulation trustworthy?"** → KAIST ground-truth-point calibration + Allan-variance parameters (the crux, the most effort).
- **Knife 3 — "isn't this just parameter tuning?"** → the anti-cherry-pick discipline (PAPER_MATERIAL material 2).
