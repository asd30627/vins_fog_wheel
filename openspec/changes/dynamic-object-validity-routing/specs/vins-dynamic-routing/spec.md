## ADDED Requirements

### Requirement: VINS feature routing acts on LEFT image only, via bbox suppression
Dynamic object routing into the VINS pipeline SHALL act by suppressing FAST/BRIEF feature extraction within the object's bounding box in the **LEFT image only**. Right image features and disparity are not directly masked. The masking is applied at the input to the feature tracker (before tracking), not as a post-processing filter on tracked features.

This matches the existing `paper2_carla_stereo_player_masked.py` implementation: per-frame JSON of bboxes is applied to the LEFT image before publication to the VINS feature tracker topic.

#### Scenario: Masking suppresses features before tracking
- **WHEN** a bbox is in the REJECT routing set for frame N
- **THEN** no FAST corners are extracted within the bbox in the LEFT image at frame N
- **AND** any feature tracked FROM a previous frame that falls within the bbox is dropped (track broken)
- **AND** the right-image disparity computation is unaffected

#### Scenario: VINS runs without masking when routing policy is ACCEPT
- **WHEN** all routing policies are ACCEPT (baseline condition)
- **THEN** the VINS output SHALL be byte-identical to the no-mask baseline
- **AND** this MUST be verified for each new recording before any masked variant is run

---

### Requirement: Variant experiment nomenclature is fixed and consistent
All VINS routing variants SHALL use the names defined in design.md. No ad-hoc renaming.

| variant key | mask content | runtime-deployable |
|---|---|---|
| `baseline` | none | yes |
| `all_object` | all YOLO detections | no (needs GT match) |
| `oracle` | GT-confirmed moving | no (needs GT) |
| `random_control` | same count+size, random positions | no (control only) |
| `raw_speed_gate` | detections with raw_speed > 1.0 m/s | baseline |
| `tcsv_m_hard` | TCSV-M REJECT set | yes (formal method) |
| `tcsv_m_soft` | TCSV-M DOWNWEIGHT set | yes (formal method) |
| `backend_cull_off` | no mask; disables 3-px cull | ablation only |
| `huber_off` | no mask; disables Huber loss | ablation only |

#### Scenario: raw_speed_gate is a baseline, not TCSV-M
- **WHEN** a result from `raw_speed_gate` is reported
- **THEN** it SHALL appear in the "baseline comparisons" section, not the "formal method" section
- **AND** TCSV-M SHALL be compared against raw_speed_gate to show it learns something beyond raw speed

---

### Requirement: DET2 determinism must be verified per recording before life gate experiments
Before any masked variant is run on a new recording, the VINS baseline MUST be verified to be deterministic (DET2) by running ×2 reps and confirming:
- `n_vio` equal in both reps
- `early_scale` equal or within 0.01 in both reps
- ATE difference < 3% between reps

If DET2 variance > 3%, a third rep is required and median is taken. If variance remains > 5% after 3 reps, the town is classified NONDETERMINISTIC_R7 and excluded from life gate experiments.

#### Scenario: New town passes DET2 gate
- **WHEN** rep1 ATE = 25.3 m and rep2 ATE = 25.7 m (difference 1.6%)
- **THEN** the town is VINS_READY_R7 and may enter vision sensitivity experiments
- **AND** the baseline ATE is recorded as median(rep1, rep2) = 25.5 m

#### Scenario: New town fails DET2 gate
- **WHEN** rep1 ATE = 25.3 m and rep2 ATE = 48.7 m (difference 93%)
- **THEN** the town is NONDETERMINISTIC_R7
- **AND** it SHALL NOT enter vision sensitivity experiments
- **AND** it SHALL be reported in the final decision document under EXCLUDED

---

### Requirement: Vision sensitivity gate threshold is ≥5% ATE change for VISION_ACTIVE, with random_control control
The minimum detectable signal threshold for declaring VISION_ACTIVE is 5% ATE reduction. A 5% threshold is chosen because:
- DET2 variance in passing towns is typically < 3%
- SNR must be ≥ 1.67 (5% signal / 3% noise)
- Town01 showed −14.3% under industrial_fog — well above threshold
- Town06/07 showed < 1% — well below threshold

`random_control` must NOT cross the same threshold (−5% or better), otherwise the result is AMBIGUOUS (cannot distinguish object-specific from feature-count artifact).

#### Scenario: VISION_ACTIVE with object-specific signal
- **WHEN** all_object reduces ATE by −8.3% AND random_control reduces ATE by −0.9%
- **THEN** the town is classified VISION_ACTIVE under that grade
- **AND** the signal is labelled object-specific (random_control ruled out)

#### Scenario: AMBIGUOUS — random_control also improves
- **WHEN** all_object reduces ATE by −7.1% AND random_control reduces ATE by −5.8%
- **THEN** the town is classified AMBIGUOUS
- **AND** it SHALL NOT be declared VISION_ACTIVE
- **AND** the result must be investigated (possible feature-density artifact)

#### Scenario: VISION_INERT
- **WHEN** all_object changes ATE by −0.6% and random_control changes ATE by −1.4%
- **THEN** the town is classified VISION_INERT
- **AND** it is suitable only as a boundary/negative control

---

### Requirement: Stock Huber + stock 3-px cull are the formal method configuration
All formal results (baseline, masked variants, TCSV-M) SHALL use:
- Huber robust loss: enabled (delta=1.0, as compiled)
- Backend outlier culling: enabled (3-px threshold, as compiled)

Any experiment with `huber_off` or `backend_cull_off` is an **ablation** and must be labelled as such in every table and figure. It shall not be used to compute the headline ATE of any formal variant.

#### Scenario: Ablation runs are labelled
- **WHEN** `huber_off` results are reported in a table
- **THEN** the table header or footnote SHALL say "ablation — not formal method"
- **AND** the row SHALL NOT appear in the main results table without an explicit ablation section label

---

### Requirement: TCSV-M is the final trained object-validity classifier; it must outperform raw baselines
TCSV-M (TCSV Masking) is the formal method in Phase 4. For TCSV-M to be a publishable contribution, it must:
1. Reduce ATE by ≥5% vs `baseline` (same threshold as VISION_ACTIVE gate)
2. Outperform `raw_speed_gate` by ≥3% ATE (it learns more than speed alone)
3. Outperform `cv_smoothing_gate` by ≥3% ATE (it learns more than smoothed speed)
4. NOT be matched by `random_control` (drop count matched, random positions)
5. Reach ≥50% of oracle gain (quantifies how much of the theoretical maximum it achieves)

#### Scenario: TCSV-M meets all bars
- **WHEN** baseline ATE = 30.0 m, oracle ATE = 25.0 m (oracle gain = 5.0 m)
- **AND** TCSV-M ATE = 27.2 m (−9.3% vs baseline, ≥50% of oracle gain = 2.5 m → 2.8 m achieved)
- **AND** raw_speed_gate ATE = 28.8 m (−4.0%), cv_smoothing ATE = 28.5 m (−5.0%)
- **AND** TCSV-M vs raw_speed: −9.3% vs −4.0% = 5.3% better → meets ≥3% bar
- **THEN** TCSV-M is a publishable contribution meeting all formal bars
