# Paper-2 Phase-0 GO conclusion — strict self-audit (2026-06-29)

Verdict: **GO → DOWNGRADE to CONDITIONAL.** Effect is real but narrower than claimed; one core attribution (FOG-hardware vs config) is NOT disentanglable with existing data.

## 疑點一 — FOG-yaw direction consistency: NOT universal (scene-dependent)
Per-seq FOG vs xsens yaw (deg), all 11:
- FOG better (urban, converged): urban26 4.8→1.0, urban28 10.9→1.3, urban29 1.3→0.3, urban30 2.5→1.2, urban38 36→0.8(rescue)
- FOG WORSE (highway): urban19 0.6→4.1, urban21 0.9→2.9
- FOG BREAKS: urban18 2.8→84.7, urban22 17→85
- both diverge: urban24
- Pattern: **FOG helps feature-rich URBAN (rotation/turning); hurts or diverges on HIGHWAY (fast, straight, few features).**
- → Claim must narrow to "FOG improves ego-yaw in feature-rich urban driving", NOT universally.

## 疑點二 — config vs FOG hardware: gyr_n confound RULED OUT, gyr_w confound REMAINS (cannot disentangle)
Built-in VINS noise profiles (parameters.cpp):
- xsens:     ACC_N 0.1, GYR_N 0.001, GYR_W 1e-4
- fog_xsens: ACC_N 0.1, GYR_N 0.001, GYR_W 1e-5  (10× lower bias-RW)
- **GYR_N is IDENTICAL → the first-paper "trust-gyro-via-low-gyr_n" confound is RULED OUT.**
- Difference = GYR_W (bias random walk), 10× lower for FOG = correct modelling of FOG bias stability, but BUNDLED with the FOG gyro data.
- **Also found: the prior "-36%" used a CONTAMINATED xsens baseline** — `p1_factors/_work/imu` is a scratch dir mixing real-xsens AND general_imu-degraded gyro across seqs (urban26/29 = general_imu, urban28/30/19 = real xsens). The -36% aggregate is unreliable.
- Clean recompute (real-xsens `kaist_vio/base` vs real-FOG `_work/fog`): FOG better on 4/4 converged urban (urban26 2.86→0.95, urban28 6.70→1.27, urban29 0.86→0.34, urban30 1.91→1.17). Direction survives, BUT cross-pipeline (different batches) and only 4 urban seqs.
- **CANNOT disentangle FOG-hardware vs gyr_w-config with existing runs** (no xsens-data+fog-config or fog-data+xsens-config run exists). Per the brief's own criterion → FOG role must be written as "high-grade gyro + its bias-stable noise model", NOT "FOG hardware itself", UNTIL a control run isolates it.

## 疑點三 — KITTI as 3rd platform: existing run SEMI-DIVERGED
drive0018 vio.csv: path ratio 1.008 (horizontal OK) BUT z drifts 454m (car should be flat) → attitude corrupted → the 20° yaw is partly a bad run, not pure convention. **KITTI not usable as a clean yaw platform without a re-run.**

## 疑點四 — object-speed splicing: RESOLVED (concern dissolves)
Object POSITION/localization error = d·sin(yaw_err) — depends ONLY on ego-yaw error and object distance, **NOT object speed**. CARLA object speed (6.87 m/s) only entered the SECONDARY velocity-estimation sub-claim. → The core position claim is KAIST-yaw × geometric-distance, no cross-dataset splicing. ✓ Clean.

## What CAN be claimed
- On feature-rich urban driving, a FOG gyro WITH its bias-stable noise model gives lower ego-yaw error than xsens (4/4 clean urban seqs; urban28 6.7°→1.3°).
- This propagates to object localization error via geometry (yaw×distance, speed-independent): at the urban yaw levels, ~0.2–0.5m at 20–50m.

## What CANNOT (yet) be claimed
- "FOG improves yaw" universally — FALSE on highway (worse/diverges).
- The gain is from FOG hardware specifically — bundled with gyr_w config, NOT disentangled.
- A clean −36% magnitude — contaminated baseline; clean set = 4 urban seqs only.
- A 3rd real-driving platform — KITTI run semi-diverged.

## To restore a clean GO (control run needed)
1. **Disentangle config vs FOG**: run xsens-gyro-data + fog_xsens config (gyr_w 1e-5) on the 4 urban seqs. If yaw stays high → gain is FOG hardware; if yaw drops → gain is the gyr_w config.
2. **Clean matched baseline**: re-run real-xsens vs real-FOG in ONE batch/pipeline across all converged urban seqs (not the contaminated _work scratch).
3. (optional) KITTI tracking (downloading) for a real-object-tracklet single-dataset object-propagation check.
