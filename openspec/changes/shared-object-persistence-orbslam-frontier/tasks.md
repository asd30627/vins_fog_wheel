# Tasks — shared-object-persistence-orbslam-frontier

Gates are sequential. Do not start a gate before the previous gate's GO criterion is met
and recorded. Do not implement beyond the current gate.

## 1. Gate 0 — Repo / dependency sanity

- [ ] 1.1 Verify `~/orbslam_ws` builds; record current wrapper commit and the uncommitted
      TUM-logger diff status.
- [ ] 1.2 Verify `~/nav2_ws` builds; record that `wavefront_explorer` runs against stock
      Nav2 costmap; document current topic rates actually observed.
- [ ] 1.3 Reproduce and document the ORB-SLAM3 shutdown global-BA hang (repro recipe +
      stack trace); timebox a fix attempt; if unfixed, standardize the SIGINT/SIGKILL
      wrapper so downstream gates are not blocked.
- [ ] 1.4 Record baseline B1 re-run on one CARLA sequence and one KITTI sequence with
      existing scripts; confirm ATE pipeline (`evo_ape`) reproduces logged numbers.
- GO criterion: both workspaces build; B1 reproduces; hang has a documented workaround.

## 2. Gate 1 — ORB-SLAM3 diagnostic export

- [ ] 2.1 Add wrapper-level per-keyframe publisher: keyframe id, pose, keypoint pixel
      locations, MapPoint ids + 3D positions + observation links. Wrapper-only if possible;
      minimal read-only core accessors otherwise (log in PATCHES.md).
- [ ] 2.2 Verify export does not worsen the shutdown hang and does not change trajectory
      output (flag off = bit-comparable TUM on an isolated re-run).
- [ ] 2.3 Add offline association tool: project per-det tracks (existing per-det CSV) onto
      exported keypoints/MapPoints; implement observation-voting ownership.
- GO criterion: per-keyframe observations with object ownership are exportable on one CARLA
  and one KITTI sequence.

## 3. Gate 2 — Contamination diagnostic (headroom check)

- [ ] 3.1 Compute on ≥3 dynamic-heavy CARLA sequences and ≥2 KITTI Tracking sequences:
      dynamic feature ratio, object-region feature ratio, MapPoint contamination ratio,
      moving-object MapPoint survival time, object-region residual distribution, count of
      object descriptors entering BoW.
- [ ] 3.2 Investigate the `BAD LOOP!!!` rejection on `Town01__dynamic_v3loop__runlong_fix4`;
      record root cause or mark loop-precision metrics conditional.
- [ ] 3.3 NO-GO check: if long-term-map contamination < ~5% in all dynamic-heavy scenes,
      STOP and redesign CARLA scenarios before proceeding.
- GO criterion: contamination headroom demonstrated on at least one suite; diagnostic
  numbers archived for the paper's motivation section.

## 4. Gate 3 — B4 baseline + two-sided anchor-recovery gate

- [ ] 4.1 Implement B4: geometric / optical-flow dynamic mask (e.g., sparse-flow +
      epipolar/reprojection consistency on tracked features), same mask-JSON interface as
      existing generators.
- [ ] 4.2 Record one new CARLA stop-and-go suite (vehicles stopping at signals then
      departing; collector flag added); pedestrians optional, do not block on walkers.
- [ ] 4.3 Assemble suites: dense-dynamic (contamination side), low-texture + parked
      (starvation side, reuse `npc_static_frac`), stop-and-go (predictive side).
- [ ] 4.4 Run offline B1 / B3 / B4 / rule-anchor prototype (mask-level approximation is
      acceptable at this gate) on all suites.
- [ ] 4.5 Evaluate two-sided gate criteria (design Decision 10); record verdict.
- GO criterion: Side A and Side B both demonstrated; rule-anchor matches or beats the best
  baseline on both suites. NO-GO: C1 downgrades to hygiene-only; escalate to user before
  proceeding.

## 5. Gate 4 — Minimal object-conditioned ORB-SLAM3 backend

- [ ] 5.1 Online keypoint labeling in wrapper (track-state interpolation between
      detections); MapPoint ownership voting online; UNKNOWN until resolved.
- [ ] 5.2 Frame-level transient exclusion in pose optimization, flag-gated.
- [ ] 5.3 Fallback ladder with triggers and hysteresis (design Decision 5).
- [ ] 5.4 Transient MapPoint lifecycle: no long-term map insertion, accelerated culling.
- [ ] 5.5 Candidate-anchor promotion (rule persistence) and demotion (design Decision 6);
      residual BoW contamination measured, not cleaned.
- [ ] 5.6 BoW / loop-closure hygiene with deferred loop-DB insertion + 300 ms timeout
      (design Decision 7); measure how often the timeout path fires.
- [ ] 5.7 Optional: three-level Local BA observation weighting; sweep anchor weight
      0.3 vs 0.5.
- [ ] 5.8 Bit-comparability check: flag off reproduces B1 on an isolated run.
- GO criterion: P1 (backend-only, rule persistence) beats or matches best baseline on the
  Gate 3 suites without regressions on benign sequences.

## 6. Gate 5 — Localization-risk-aware frontier utility

- [ ] 6.1 New anchor-store node beside `paper2_validity_bridge` exposing the raw object
      layer and the anchor layer as separate topics (design Decision 3).
- [ ] 6.2 Modify `wavefront_explorer` goal scoring to the four-term utility with per-cycle
      normalization (design Decision 8).
- [ ] 6.3 Implement localization risk on known traversal segments only + liveness rule;
      unit-test the exploration deadlock rule on a synthetic map.
- [ ] 6.4 Implement P2 mode (raw layer + vanilla map density only) and P3 mode (anchor
      layer); enforce the signal boundary in code (P2 build cannot subscribe anchor topics).
- GO criterion: in a controlled scenario, P2/P3 select measurably different frontiers than
  information-gain-only, and exploration does not stall.

## 7. Gate 6 — Learned persistence / anchor eligibility

- [ ] 7.1 Build training set from Gates 2–5 logs; CARLA labels from GT actor motion over a
      fixed horizon (visibility loss is not motion); KITTI parked/moving validation split.
- [ ] 7.2 Train per-track GRU / temporal CNN; outputs per design Decision 9.
- [ ] 7.3 Compare rule vs learned vs CARLA-oracle persistence on downstream endpoints
      (backend metrics on Gate 3 suites; planner decisions on Gate 5 scenario).
- [ ] 7.4 Apply downgrade rule if learned does not beat rule (record verdict; C3 becomes
      analysis).
- GO criterion: verdict recorded either way; oracle shows headroom.

## 8. Gate 7 — Closed-loop CARLA + offline KITTI evaluation

- [ ] 8.1 Stabilize Nav2-in-loop: root-cause the ~11.5 s batch exit or establish a scripted
      interactive protocol; potential-field harness is dev-only and excluded from results.
- [ ] 8.2 Port CARLA synchronous-mode + fixed-seed logic (from `collect_carla_v2.py`) into
      the closed-loop harness.
- [ ] 8.3 Run full ablation matrix (B1–B5, P1–P7) on 2 suites × ≥5 seeds; pruned rows
      (B1/B3/B4/P3/P4) on remaining suites.
- [ ] 8.4 Compute coupling gains and coupling residual per primary endpoint.
- [ ] 8.5 Offline KITTI Tracking evaluation (localization + persistence validation).
- [ ] 8.6 Compile localization / navigation / integrity metric tables; mark loop-precision
      conditional per Gate 2 outcome; mark all edge-rate numbers as planning targets.
- GO criterion: closed-loop tables complete; coupling residual reported; paper-ready
  evidence pack archived.

## 9. Flow Review

- [ ] 9.1 [Flow Review] Re-read proposal.md, design.md, all four specs, and this tasks.md
      end-to-end; verify no contradiction with the signal boundary (Decision 3), the
      exploration deadlock rule (Decision 8), and the standing-rulings section; smooth any
      inconsistencies.
