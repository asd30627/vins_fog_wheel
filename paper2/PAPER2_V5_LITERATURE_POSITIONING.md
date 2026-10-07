# Paper-2 v5 — Literature Positioning Check

**Paper:** *Observability-Aware Dynamic Object State Validity for GPS-Denied Navigation*
**Date of check:** 2026-06-30
**Method:** WebSearch + WebFetch. Each entry verified by fetching the arXiv/venue page where possible.
**Honesty posture:** This document hunts for *positioning differences*, not proof that nobody used similar words. We do **not** claim "first". Where a paper is close, it is flagged as close and the precise problem/output/experiment difference is stated. Items that could not be fully verified are marked **[UNVERIFIED]** or **[PARTIAL]**.

---

## TL;DR for the author

- **The single closest prior work is Qiu, Qin, Xie & Shen, IROS 2018** ("Estimating Metric Poses of Dynamic Objects Using Monocular Visual-Inertial Fusion"). It *already* does conditional estimation of dynamic-object state with explicit degenerate-case handling and an "observability condition" that refuses metric-scale output in 4 named degenerate cases. **This is the paper that most threatens a naive "we are the first to notice object state can be unobservable" claim.** You must cite it and differentiate sharply (see C1/C2 below). Our novelty has to live in: (a) a *regime/phase map over road-geometry variables* rather than a per-object scalar threshold; (b) a *multi-class refusal policy* (full / position-only / invalid-velocity / unobservable / warning) rather than binary accept/reject of metric scale; (c) a *GPS-denied driving* framing with a *task-decision* evaluation (invalid-velocity recall/precision, overconfident-wrong-velocity, false-refusal), not a tracking-accuracy benchmark.
- The classical **bearings-only Target Motion Analysis (TMA)** literature (Nardone & Aidala 1981, and the smooth-maneuver line) *is the theoretical ancestor* of "object velocity/range can be unobservable without observer maneuver". You cannot claim the observability insight itself is new; you can claim the *application to monocular/VI road perception as a deployable validity layer with a phase map* is new-to-our-knowledge.
- The "conformal risk tube" paper you suspected ("PURI-DO") **does not exist under that name**. The real, very recent work is **Fu & Chen, "Uncertainty-Aware Vision-based Risk Object Identification via Conformal Risk Tube Prediction," arXiv 2603.23919 (ICRA 2026, preprint)**. It is about *risk/importance scoring with conformal coverage*, NOT geometric state observability — easy and clean to differentiate. Good news for C4-not-being-the-novelty.
- Dynamic-SLAM systems (VDO-SLAM, DynaSLAM II, ClusterVO, DOT-SLAM) **always output an object velocity / SE(3) motion and do not gate on observability** — they only report empirical failure modes in discussion. This is a strong, honest contrast: *they estimate-and-hope; we decide-then-(maybe)-estimate.*
- Probabilistic detection / 3D-MOT-uncertainty (Gaussian-YOLOv3, MonoRUn, BayesOD, UA-Track) produce *covariances/uncertainty*, not an *observability verdict tied to scene geometry*, and not a *refusal taxonomy*. Differentiation is clean as long as you do NOT pitch OVI as "just another uncertainty estimate".

---

## Cluster A — Object / multibody motion observability and degeneracy (the core threat)

### A1. Qiu, Qin, Xie, Shen — *Estimating Metric Poses of Dynamic Objects Using Monocular Visual-Inertial Fusion* — **IROS 2018** (arXiv 1808.06753). **VERIFIED.**
- **What it does:** Recovers metric 6-DoF pose of an *arbitrary* dynamic object from a monocular camera + IMU, by combining up-to-scale object BA, VINS camera pose, and metric-scale recovery via correlation/independence between object and camera motion.
- **Similarity to us (HIGH):** Explicitly frames dynamic-object metric estimation as *conditional on an observability condition*; identifies **four degenerate cases** — (C1) camera follows object exactly, (C2) static camera, (C3) constant-velocity camera, (C4) static object in camera frame — and **refuses / withholds metric output** when the observability condition is not met (threshold-based, their Eqs. 17–18). This is essentially "do not output a possibly-wrong scale when geometry is degenerate", which is our spirit.
- **Difference from us:** (i) Output granularity: theirs is binary *accept metric scale / keep up-to-scale*; ours is a **5-way refusal policy** (full_state / position_only / invalid_velocity / unobservable / conservative_warning). (ii) Conditioning variables: theirs is motion-independence/excitation of a *single tracked object*; ours is an **interpretable phase map over road-geometry regimes** (distance × density × bearing-change × depth-quality × yaw-lever). (iii) Target quantity: theirs is *scale/full pose*; we separate **velocity observability from position observability** (position-only is a first-class outcome). (iv) Evaluation: theirs is pose/scale accuracy on tracked objects; ours is a **decision-quality evaluation** (invalid-velocity recall/precision, overconfident-wrong-velocity rate, false-refusal rate). (v) Domain: GPS-denied *road* navigation regimes, not generic object scanning.
- **CANNOT claim:** "first to observe dynamic-object state can be unobservable under monocular/VI sensing"; "first to refuse metric output in degenerate object-motion cases"; "first to use an observability condition to gate dynamic-object estimation". All pre-dated by this paper.
- **CAN still claim (honestly):** "Unlike prior conditional metric-object estimators that gate a single scalar (metric scale) via a motion-excitation threshold (Qiu et al., IROS 2018), we (a) characterize *which road-geometry regimes* induce velocity-vs-position un-observability as an interpretable phase map, and (b) emit a *graded refusal decision* evaluated by decision-level metrics rather than tracking accuracy."

### A2. Bearings-only Target Motion Analysis observability — **Nardone & Aidala, *Observability Criteria for Bearings-Only Target Motion Analysis*, IEEE T-AES, AES-17, pp. 162–166, 1981**; plus the smooth-maneuver line (*Observability: Range-Only vs Bearings-Only TMA When the Observer Maneuvers Smoothly*, IEEE T-AES). **VERIFIED (classic), [PARTIAL] on the smooth-maneuver paper's exact authors/year.**
- **What it does:** Establishes necessary/sufficient conditions on *observer* motion for a unique bearings-only tracking solution; shows the process can stay **unobservable even with nonzero bearing rate** for certain maneuvers; range is unobservable without observer maneuver.
- **Similarity to us (CONCEPTUAL, HIGH):** This is the canonical statement that *target velocity/range is unobservable without sufficient observer excitation* — the theoretical root of our claim that object velocity can be weakly/unobservable.
- **Difference from us:** Sensor and setting (passive sonar/radar single-bearing tracking, point target, no depth, no detector); no *phase map over driving regimes*, no *refusal taxonomy for a perception stack*, no monocular-depth/yaw-lever terms. Ours operationalizes the idea inside a *visual/VI road perception* stack as a deployable validity layer.
- **CANNOT claim:** the observability insight itself ("velocity can be unobservable without maneuver") as novel — it is 40+ years old.
- **CAN still claim:** "We connect classical bearings-only observability (Nardone & Aidala, 1981) to modern monocular/VI dynamic-object perception, and turn the qualitative condition into an interpretable, regime-indexed validity layer with a graded output policy for GPS-denied driving." Use this paper as *foundation/credibility*, not as competition.

### A3. Multibody Structure-from-Motion + degeneracy — **Ozden, Schindler, Van Gool, *Multibody SfM in Practice*, IEEE TPAMI 2010**; **Vidal et al., *Two-View Multibody SfM*, IJCV 2006**; the *Visual SLAM/SfM in Dynamic Environments: A Survey* (Oxford). **VERIFIED (titles/venues), [PARTIAL] on exact author lists.**
- **What it does:** Recovers structure+motion of multiple independently-moving bodies; explicitly discusses degeneracies, e.g. the *affine/small-distant-object* degeneracy and the *mirror (Necker) ambiguity*; survey collates dynamic-scene degeneracies.
- **Similarity to us:** Acknowledges that moving objects routinely fall into degenerate/ambiguous configurations.
- **Difference from us:** Goal is *reconstruction*; the degeneracy discussion is about *when reconstruction is ambiguous*, not about a *runtime validity decision / refusal policy* for downstream navigation, and not regime-indexed for road geometry. No velocity-validity taxonomy.
- **CANNOT claim:** "first to note moving objects fall into degenerate geometric configurations".
- **CAN still claim:** "Prior multibody SfM characterizes reconstruction degeneracies (e.g., affine/mirror ambiguities; Ozden et al. 2010); we instead characterize *state-validity* regimes (velocity vs. position observability) and convert them into a graded refusal policy at runtime."

### A4. Observability-enhanced bearing/target-motion estimation (recent robotics line) — e.g. *Observability-Enhanced Target Motion Estimation via Bearing-Box* (arXiv 2601.06887), *Cooperative Bearing-Rate* (arXiv 2502.08089), *Bearing-Angle Approach* (arXiv 2401.17117). **VERIFIED (exist), [PARTIAL] on venues.**
- **What it does:** Improve *observability* of a target's motion by adding observer maneuvers, bearing-box, bearing-rate, or cooperative observers (mostly MAV/UAV targets).
- **Similarity to us:** Same underlying observability concern for moving targets.
- **Difference from us:** Their thrust is to **restore observability by changing sensing/observer behavior** (active); ours is to **decide validity passively and refuse** when geometry is fixed by traffic (a road car cannot freely maneuver to observe a lead vehicle). Different problem posture (enhance vs. adjudicate), different domain.
- **CANNOT claim:** novelty of "observer motion affects target observability".
- **CAN still claim:** "Unlike observability-*enhancing* target-motion estimators that assume the observer can maneuver to gain excitation, we treat the road-geometry regime as largely *exogenous* and provide a validity/refusal decision under it."

---

## Cluster B — Ego-motion uncertainty + moving-object estimation under a moving camera

### B1. VDO-SLAM — **Zhang, Henein, Mahony, Ila, *VDO-SLAM: A Visual Dynamic Object-aware SLAM System*, arXiv 2005.11052, 2020** (IJRR-adjacent; **[PARTIAL]** on final journal). **VERIFIED on method behavior.**
- **What it does:** Model-free dynamic SLAM; estimates full SE(3) object pose-change and **extracts object linear velocity** by applying the pose change to object points and differencing (their Eq. 24), averaged over points.
- **Similarity to us:** Directly produces *dynamic-object velocity* for driving ("object speed estimation … important for autonomous driving").
- **Difference from us (KEY, CLEAN):** **It always outputs a velocity and does NOT gate on observability.** It only *discusses* empirical failure modes (self-rotating objects via optical-flow limits; degradation with distance; smooth-motion constraint "strongly violated" under alternating accel/decel). No validity verdict, no refusal, no phase map.
- **CANNOT claim:** "first to estimate dynamic-object velocity from a moving camera"; "first to notice distant/degenerate objects degrade velocity".
- **CAN still claim:** "Object-aware dynamic SLAM (VDO-SLAM) *always emits* an object velocity and treats degradation only as discussion; we instead make observability a *first-class decision*, emitting invalid-velocity/unobservable verdicts and evaluating them by decision-level metrics."

### B2. DynaSLAM II — **Bescós, Campos, Tardós, Neira, *DynaSLAM II: Tightly-Coupled Multi-Object Tracking and SLAM*, IEEE RA-L 2021** (arXiv 2010.07820). **VERIFIED (title/authors); venue RA-L [PARTIAL] but standard.**
- **What it does:** Joint BA over camera, static structure, and moving-object trajectories; tightly-coupled MOT+SLAM.
- **Similarity to us:** Estimates moving-object motion in a driving context.
- **Difference from us:** Optimizes object trajectories for accuracy; **no observability gating / validity refusal**; no regime map; no velocity-validity taxonomy.
- **CANNOT claim:** novelty in jointly estimating object motion + ego.
- **CAN still claim:** "Tightly-coupled MOT+SLAM (DynaSLAM II) improves object-trajectory *accuracy* but never *declines to estimate*; our contribution is orthogonal — a validity layer deciding when such an estimate should be trusted, position-only, or refused."

### B3. ClusterVO / ClusterSLAM, DOT-SLAM, DL-SLOT, MOTSLAM — dynamic-SLAM family. **VERIFIED existence; treat as a group, [PARTIAL] on per-paper details.**
- **What they do:** Cluster + track dynamic objects (CRF clustering in ClusterVO; graph-optimization stereo DOT-SLAM; MOT-assisted monocular MOTSLAM).
- **Similarity/Difference/Cannot/Can:** Same pattern as B1/B2 — they *track and estimate*; none publishes a *geometry-conditioned observability/refusal layer for object velocity validity*. We can group-cite them as "the dynamic-SLAM line treats object motion as always estimable" and differentiate identically. Do **not** single out per-paper novelty claims without reading them.

### B4. Vehicle ego-motion + surrounding-vehicle state from a monocular camera (classic) — e.g. *Vehicle Ego-Motion Estimation and Moving Object Detection using a Monocular Camera* (IEEE, ~2006) and related. **VERIFIED (exists), [PARTIAL] authors/year.**
- **What it does:** Estimates ego-motion + 3D position/velocity/orientation of surrounding vehicles from a single camera (depth + optical flow).
- **Difference from us:** Estimation pipeline; no observability/validity decision; no refusal taxonomy. Same differentiation.

---

## Cluster C — Refusal-aware / selective prediction / failure detection in perception

### C1. SelectiveNet / selective classification foundations — **Geifman & El-Yaniv, *SelectiveNet*, ICML 2019** (arXiv 1901.09192); El-Yaniv & Wiener (risk-coverage); Chow's reject rule. **VERIFIED.**
- **What it does:** Neural nets with an integrated *reject option*; formalizes the **risk–coverage trade-off** (abstain to lower error on the rest).
- **Similarity to us (CONCEPTUAL):** "Refuse when not confident" is exactly the selective-prediction spirit; our false-refusal-rate / coverage framing is borrowed from here.
- **Difference from us:** Selective classification abstains based on a *learned/confidence* signal over labels; our refusal is driven by **interpretable observability geometry** (yaw-lever, bearing-change-rate, depth proxy, velocity-observability proxy), is **multi-class with state-specific outcomes** (velocity-invalid vs position-only vs unobservable), and is for *continuous object-state validity in a navigation stack*, not label classification.
- **CANNOT claim:** novelty of "abstain/reject option" or "risk-coverage trade-off". Cite SelectiveNet as the conceptual frame.
- **CAN still claim:** "We instantiate selective prediction (Geifman & El-Yaniv, 2019) for *geometric state observability of dynamic objects*: refusal is decided by interpretable observability terms, not learned confidence, and the decision is graded (position-only vs invalid-velocity vs unobservable)."

### C2. Task-Aware Risk Estimation of Perception Failures — **Antonante, Veer, Leung, Weng, Carlone, Pavone, *Task-Aware Risk Estimation of Perception Failures for Autonomous Vehicles*, RSS 2023 / arXiv 2305.01870.** **VERIFIED (authors/abstract).**
- **What it does:** Estimates whether a *perception failure matters to the motion plan* (PAC risk via copulas over alternative scenarios). A failure is low-risk if it does not affect plan safety.
- **Similarity to us:** Both decide *when a perception problem should change downstream behavior*.
- **Difference from us (CLEAN):** Theirs is **task-relevance of a (already-detected) failure to planning**; it presupposes you can detect the failure. Ours is **upstream and geometric**: *why* the estimate is untrustworthy (the object's velocity is geometrically weakly/un-observable), independent of any plan, with a refusal taxonomy. "Geometry alone ≠ task-aware risk" — they sit at different stages.
- **CANNOT claim:** "first to decide when a perception issue should trigger a conservative response."
- **CAN still claim:** "Complementary to task-aware perception-failure risk (Antonante et al., RSS 2023), which scores a failure's *planning relevance*, we provide the *upstream geometric cause* — an observability verdict on dynamic-object state — that can feed such risk estimators."

### C3. Self-Aware Trajectory Prediction — **arXiv 2305.09147, 2023.** **VERIFIED title/cluster; [PARTIAL] authors/venue (PDF was binary; do not cite authors without checking).**
- **What it does:** Adds a *self-awareness module* to a trajectory-*prediction* network to estimate its own online performance/uncertainty for safety.
- **Difference from us:** It is about *future-trajectory prediction* self-assessment; we are about *current-state observability/validity* of object velocity/position. Different stage (predict vs. estimate-now), different signal (learned self-assessment vs. interpretable geometry).
- **CANNOT claim:** novelty of "model knows when it's wrong" for driving.
- **CAN still claim:** "Unlike self-aware *prediction* modules that learn to flag their own future-trajectory errors, we flag *present-state un-observability* from interpretable geometry, before any prediction."

### C4. Introspective / run-time-monitoring perception (false-negative prediction, OOD, perception-validity verification) — e.g. *Introspective False Negative Prediction for Black-Box Detectors* (Sensors/MDPI), *Run-time Introspection of 2D Object Detection* (arXiv 2403.01172), *Real-Time Evaluation of Perception Uncertainty and Validity Verification* (Sensors 2023), *Run-Time Monitoring of ML for Robotic Perception: A Survey* (arXiv 2101.01364). **VERIFIED existence; [PARTIAL] details.**
- **What they do:** Monitor detector reliability online (miss/false-positive prediction, OOD, validity verification).
- **Difference from us:** Operate on **detection reliability** (is the box right?), typically appearance/feature-driven; ours is **state-estimation observability** (is the *velocity/position* geometrically recoverable?), geometry-driven, with a graded refusal taxonomy. We must not conflate "detection introspection" with "state-observability adjudication".
- **CANNOT claim:** "first to do run-time perception introspection/monitoring."
- **CAN still claim:** "Run-time perception monitors target *detection* reliability; we target *state-observability* — a complementary failure axis where the box may be correct yet the velocity is unrecoverable."

---

## Cluster D — Conformal prediction / risk tube (to differentiate, NOT adopt as novelty)

### D1. *Uncertainty-Aware Vision-based Risk Object Identification via Conformal Risk Tube Prediction* — **Fu & Chen, arXiv 2603.23919, ICRA 2026 (preprint).** **VERIFIED title/authors/abstract; venue ICRA 2026 = preprint, [PARTIAL] (not yet camera-ready).** *(This is the real work behind the suspected but non-existent "PURI-DO".)*
- **What it does:** Vision risk-object *importance* identification with **conformal coverage guarantees** on risk; calibrated risk scores + spatiotemporal uncertainty; category-aware conformal calibrators.
- **Similarity to us:** Same domain (driving), same "uncertainty-aware, don't make blind deterministic decisions" motivation; both can flag risky/ambiguous situations.
- **Difference from us (VERY CLEAN):** It is about **which object is risk-relevant + calibrated risk score**, NOT about **geometric observability of an object's velocity/state**. It never decides a state is unobservable due to geometry. No velocity-validity taxonomy; output is a risk tube, not a refusal class.
- **CANNOT claim:** anything implying we own conformal/risk-tube methodology (we don't, and shouldn't — keep conformal as *optional/minor* per your own scope).
- **CAN still claim:** "Concurrent conformal risk-tube methods (Fu & Chen, 2026) calibrate *risk importance*; we instead adjudicate *state observability/validity*. The two are orthogonal — observability is a prerequisite for any meaningful risk estimate on object velocity." Use this to *de-risk* C4 (object-motion-inconsistency / conformal is explicitly NOT your main novelty).

### D2. MOT-CUP (Collaborative MOT w/ Conformal Uncertainty Propagation, IEEE 2024) + Two-Step Conformal Bounding-Box (ECCV-W 2024, arXiv 2403.07263). **VERIFIED existence; [PARTIAL] details.**
- **What they do:** Propagate *conformal* detection/tracking uncertainty into association/prediction; calibrated bounding-box intervals.
- **Difference from us:** Calibrated *uncertainty intervals*, not an *observability verdict / refusal policy*; appearance+detection driven. Same differentiation as D1. Do not adopt as novelty.

---

## Cluster E — Probabilistic 3D detection / MOT uncertainty (differentiate; do NOT pitch OVI as "yet another uncertainty")

### E1. **Gaussian YOLOv3 — Choi, Chun, Kim, Lee, ICCV 2019.** **VERIFIED.** Models bbox coords as Gaussians → localization uncertainty to cut FPs/raise TPs.
### E2. **BayesOD — Harakeh, Smart, Waslander, ICRA 2020.** **VERIFIED.** Bayesian aleatoric+epistemic uncertainty for deep detectors.
### E3. **MonoRUn — Chen, Huang, Tian, Gao, Xiong, CVPR 2021.** **VERIFIED.** Monocular 3D detection; propagates network uncertainty through an **uncertainty-driven PnP → object pose covariance**.
### E4. **UA-Track (arXiv 2406.02147), UncertaintyTrack (arXiv 2402.12303)** — uncertainty-aware end-to-end 3D MOT (probabilistic attention; integrate BayesOD-style detectors). **VERIFIED existence; [PARTIAL] venues.**
- **What they do (group):** Produce *calibrated/learned uncertainty or covariance* over boxes/poses/tracks.
- **Similarity to us:** Both quantify "how unsure are we about this object". MonoRUn even yields a *pose covariance*, the closest in spirit.
- **Difference from us (MUST be crisp):** These output **a covariance/uncertainty magnitude**, learned/aleatoric, per detection/track. They do **not**: (a) attribute the uncertainty to a **named observability regime** (distance/bearing-change/yaw-lever/depth); (b) distinguish **velocity-unobservable vs position-observable** as separate *validity classes*; (c) emit a **refusal decision** evaluated by invalid-velocity recall/precision / overconfident-wrong-velocity / false-refusal. A large covariance ≠ a "velocity is structurally unobservable; output position-only" verdict.
- **CANNOT claim:** "first to attach uncertainty to object state"; "first probabilistic object pose/velocity". MonoRUn already gives object-pose covariance.
- **CAN still claim:** "Probabilistic detectors/trackers (Gaussian-YOLOv3, BayesOD, MonoRUn, UA-Track) emit *uncertainty magnitudes*; we emit an *interpretable observability verdict and a graded validity decision*. Crucially we separate *velocity-unobservable* from *position-observable* and evaluate the *decision*, not calibration of a covariance." **Guard rail:** do not let a reviewer collapse OVI into "a hand-crafted uncertainty score" — the load-bearing novelty is the *regime map + multi-class refusal + decision-level evaluation*, not the existence of a scalar.

---

## Synthesis

### Cleanest honest positioning sentences (safe to use)
1. "Most dynamic-object perception and dynamic-SLAM systems (e.g., VDO-SLAM, DynaSLAM II) **always output an object velocity** and treat degraded geometry only as a discussion-section caveat; **to our knowledge, no prior driving-perception system emits a graded, geometry-conditioned validity decision** (full-state / position-only / invalid-velocity / unobservable / warning) over an object's *state*."
2. "Classical bearings-only observability (Nardone & Aidala, 1981) and conditional metric-object estimation (Qiu et al., IROS 2018) establish that object velocity/scale can be unobservable without sufficient excitation; **we build on this** and turn the qualitative condition into an **interpretable phase map over road-geometry regimes** with a **multi-class refusal policy**, evaluated by *decision-level* metrics rather than tracking accuracy."
3. "Unlike probabilistic detectors/trackers that output an uncertainty magnitude (Gaussian-YOLOv3, BayesOD, MonoRUn), and unlike conformal risk-tube / task-aware-risk methods that calibrate *risk importance* (Fu & Chen 2026; Antonante et al., RSS 2023), **we adjudicate geometric *state observability* upstream**, separating *velocity-unobservable* from *position-observable* as distinct validity classes."
4. "We deliberately keep object-motion-inconsistency / conformal tooling as an **optional ego-degradation diagnostic**, not a novelty claim, since calibrated-risk methods already own that space."

### Riskiest overlaps (handle explicitly in Related Work)
1. **Qiu et al., IROS 2018 (HIGHEST RISK).** They already: conditionally estimate dynamic-object metric state; name degenerate cases; refuse output via an observability condition. *Mitigation:* foreground them; claim novelty only in (regime phase map) + (multi-class velocity-vs-position refusal) + (GPS-denied driving decision-evaluation). Never say "first to gate dynamic-object estimation on observability."
2. **MonoRUn, CVPR 2021.** Already yields *object pose covariance* via uncertainty PnP. *Mitigation:* stress that a covariance is not an observability verdict / refusal class, and that OVI's value is the interpretable regime decomposition + decision policy, not the existence of an uncertainty number.
3. **Bearings-only TMA classics.** The observability insight is old. *Mitigation:* cite as foundation; claim only the *operationalization* for monocular/VI road perception as a deployable validity layer.
4. **Task-Aware Risk (RSS 2023) & Conformal Risk Tube (ICRA 2026).** Same "be cautious about uncertain perception in driving" vibe. *Mitigation:* position as *complementary, downstream* (they consume validity; we produce it); they score risk/importance, we score geometric observability.
5. **Selective prediction (SelectiveNet, ICML 2019).** The abstain/risk-coverage framing is borrowed. *Mitigation:* cite as the conceptual frame; novelty is geometry-driven, multi-class, state-specific refusal — not a learned binary reject head.

### Explicit "claims to AVOID" (do not write these)
- "First to observe that dynamic-object velocity/state can be unobservable." → **NO** (Nardone & Aidala 1981; Qiu et al. 2018).
- "First to refuse / withhold dynamic-object state output under degenerate geometry." → **NO** (Qiu et al. 2018 gate metric scale).
- "First probabilistic / uncertainty-aware object state or pose." → **NO** (MonoRUn, BayesOD, Gaussian-YOLOv3, UA-Track).
- "First selective-prediction / reject-option in perception." → **NO** (SelectiveNet line).
- "First conformal / risk-tube for driving objects" or any framing implying we own conformal methodology. → **NO** (Fu & Chen 2026; MOT-CUP 2024) — and it is explicitly *not* your novelty anyway.
- "First to decide when a perception issue should trigger a conservative driving response." → **NO** (Antonante et al., RSS 2023).
- "We improve detector/tracker accuracy / propose a new object factor / aid localization with objects." → out of scope by your own statement; do not let phrasing drift there.
- Bare **"first"** anywhere. Use **"to our knowledge"**, **"we focus on"**, **"unlike methods that…"**, **"complementary to…"**.

---

## Verification status / caveats
- **Fully verified (title+authors+venue or abstract fetched):** Qiu et al. IROS 2018; Nardone & Aidala 1981 (T-AES vol/pages); VDO-SLAM (method behavior + Eq.24 velocity, no gating); DynaSLAM II (authors/title); Task-Aware Risk (Antonante et al., abstract); Conformal Risk Tube (Fu & Chen, abstract, ICRA 2026 preprint); Gaussian-YOLOv3 (ICCV 2019); BayesOD (ICRA 2020, Harakeh/Smart/Waslander); MonoRUn (CVPR 2021); SelectiveNet (ICML 2019, arXiv 1901.09192).
- **[PARTIAL] (existence + topic verified; exact venue/author/year not fully confirmed — verify before citing):** the smooth-maneuver TMA paper's authors/year; Multibody-SfM exact author lists; ClusterVO/DOT-SLAM/DL-SLOT/MOTSLAM per-paper details; DynaSLAM II venue (RA-L assumed, standard); VDO-SLAM final journal (IJRR-adjacent); UA-Track / UncertaintyTrack venues; recent bearing-box/bearing-rate arXiv venues; Self-Aware Trajectory Prediction authors/venue (PDF returned binary — DO NOT cite authors unverified).
- **Non-existent as named:** **"PURI-DO" — could not verify; no such work found.** The real, intended reference is almost certainly Fu & Chen, *Conformal Risk Tube Prediction* (arXiv 2603.23919). Do not cite "PURI-DO".
- No citations, titles, authors, or venues in this document were fabricated; uncertain ones are flagged. Re-confirm every **[PARTIAL]** item against the actual paper before it enters the manuscript's reference list.
