# PAPER2 R7 — Urban Candidate Decision

> R7 urban-candidate scenario search — Phase 1–5 complete.
> Date: 2026-07-02. Branch: grade-fusion-v1.

---

## 12-Question Gate Answers

### 1. Which candidate towns were MAP_AVAILABLE?

All 5: Town01, Town02, Town04, Town05, Town10HD. (Town06/07 also available but are boundary controls — not tested as positive candidates.)

### 2. Which previews passed (PASS_PREVIEW)?

| town | best variant | matched<50m | result |
|---|---|---|---|
| Town01 | dense_slow_r7_preview | 144 | **PASS_PREVIEW** |
| Town02 | dense_near_r7_preview | 585 | **PASS_PREVIEW** |
| **Town04** | dense_near (best) | 0 | **FAIL — all LOW_YIELD** |
| Town05 | dense_slow_r7_preview | 1648 | **PASS_PREVIEW** |
| Town10HD | dense_slow_r7_preview | 1073 | **PASS_PREVIEW** |

Town04 failure root cause: `--npc-skip-ego-lane` left zero near-band candidates within 50m — Town04 has wide roads where adjacent lanes are far from ego's camera frame.

### 3. Which core recordings are VINS_READY_R7?

All 4 PASS_CORE towns passed VINS smoke (DET2, ideal_imu ×2):

| town | core recording | ego path | matched<50m | ATE (rep1/rep2) | class |
|---|---|---|---|---|---|
| Town01 | dense_slow_r7_core | 150.9 m | 470 | 34.19 / 34.19 m | **VINS_READY_R7** |
| Town02 | dense_near_r7_core | 150.8 m | 1065 | 34.23 / 34.23 m | **VINS_READY_R7** |
| Town05 | dense_slow_r7_core | 101.9 m | 3100 | 41.53 / 41.53 m | **VINS_READY_R7** |
| Town10HD | dense_slow_r7_core | 150.8 m | 2587 | 35.03 / 34.30 m | **VINS_READY_R7** |

All runs: n_vio=840, early≈0.99, late≈2.2 (deterministic).

### 4. Which towns are VISION_ACTIVE?

**None.**

### 5. Which towns are VISION_INERT?

**All 4 (both grades).**

| town | grade | baseline ATE | d_mask | d_oracle | d_rand | verdict |
|---|---|---|---|---|---|---|
| Town01 | ideal_imu | 34.61 m | −1.2% | 0.0% | −1.2% | **VISION_INERT** |
| Town01 | industrial_fog | 36.86 m | −1.2% | −1.2% | 0.0% | **VISION_INERT** |
| Town02 | ideal_imu | 34.91 m | −1.9% | 0.0% | −1.6% | **VISION_INERT** |
| Town02 | industrial_fog | 36.45 m | +0.1% | +1.0% | +0.3% | **VISION_INERT** |
| Town05 | ideal_imu | 41.53 m | −0.8% | 0.0% | 0.0% | **VISION_INERT** |
| Town05 | industrial_fog | 44.18 m | −0.7% | 0.0% | +2.0% | **VISION_INERT** |
| Town10HD | ideal_imu | 34.30 m | −0.1% | 0.0% | −0.5% | **VISION_INERT** |
| Town10HD | industrial_fog | 36.91 m | −1.2% | −1.1% | −1.5% | **VISION_INERT** |

Masking signal: all variants within ±2% ATE — well below the 5% VISION_ACTIVE threshold.

### 6. Did Town10HD replicate Town01?

**Not applicable as a fair test.** Town10HD R7 is VISION_INERT; Town01 R7 is also VISION_INERT. The comparison to replicate is against Town01 **dense_b1** (which showed −14.3% under industrial_fog, autopilot, stock recipe). Town10HD R7 cannot replicate a result from a different recording recipe — see §Critical Finding below.

### 7. Did Town02 / Town04 / Town05 show stronger signals?

No. Town02 (industrial_fog): +0.05% (masking makes it *slightly worse*). Town05 (industrial_fog): −0.72% despite 3100 matched<50m. Town04: excluded (no PASS_PREVIEW). None approached the 5% threshold.

### 8. Are Town06 / Town07 still boundary / negative controls?

Yes. Phase 2 (2026-07-01) confirmed both towns VISION_INERT for both grades. This is unchanged. They remain the boundary/negative controls.

### 9. Is there enough evidence to run TCSV life gate (Phase 4)?

**No.** Per the OpenSpec failure gate (proposal.md): *"Phase 4 only proceeds if Phase 3 produces at least one VISION_ACTIVE (town, grade) pair."* Zero VISION_ACTIVE pairs were found.

### 10. Which exact runs should enter Phase 4 (TCSV)?

**None** — Phase 4 is blocked.

### 11. Which runs should be excluded?

All R7 runs for TCSV purposes. Town04 is excluded (no PASS_PREVIEW). Town06/07 are excluded (boundary controls only). All R7 PASS_CORE runs are candidates only for understanding the measurement null, not for TCSV life gate.

### 12. Paper claim status

See §Recommended Options below. Per the OpenSpec failure gate, the default is:

> **Claim downgraded to planner/perception-facing validity only — no VINS localization contribution from this R7 dataset.**

However, there is a measurement confound (§Critical Finding) that must be resolved before accepting this as a true null.

---

## Critical Finding: R7 Recipe Confound

**The R7 VISION_INERT result is not a clean null.** It is confounded by a measurement artifact:

**Root cause: `--drive-mode gentle_turn` → late-scale drift ≈ 2.2x → ATE dominated by drift (~30m), masking signal (<1m) swamped.**

All R7 cores (Town01/02/05/10HD) show:
- `early_scale ≈ 0.99` (scale initialises correctly)
- `late_scale ≈ 2.2` (deterministic, but large drift)
- ATE ≈ 34–42m (dominated by late drift, not by dynamic-object feature corruption)

**Why `gentle_turn` causes drift:** Gentle_turn uses a pure-pursuit controller with constrained steer angle, producing long straight sections and soft curves. This gives insufficient yaw excitation for VI scale to remain observable over the full trajectory. The IMU lever-arm (1.5m, `imu_at_vehicle_center=True`) provides some excitation, but not enough on long straights.

**Why this confounds the VISION_ACTIVE test:** If ATE is dominated by a scale drift that masking cannot affect (masking suppresses FAST features; it does not affect IMU preintegration or scale observability), then masking cannot produce ≥5% ATE change even if it genuinely helps. The signal is buried under noise 15× larger than itself.

**Contrast with Town01 dense_b1 (the only positive result):**
- Recorded with `autopilot` on urban Town01 → natural turns → sufficient yaw excitation
- No late drift: ATE ≈ 2.8m
- industrial_fog masking gave −14.3% (signal-to-noise >> 1)
- This positive result is **not invalidated** by R7; it simply was not reproduced under R7 recipe conditions

**Object density is NOT the bottleneck.** Town05 has 3100 matched<50m (4× Town01 dense_b1's 777) and still shows <1% signal. The bottleneck is drift, not object count.

---

## Dataset Summary

| recording | matched<50m | late_scale | ATE baseline | d_mask (ind_fog) | verdict |
|---|---|---|---|---|---|
| Town01 dense_b1 (old, autopilot) | 777 | ≈1.0 | 2.86 m | **−14.3%** | ✅ positive signal |
| Town01 dense_slow_r7_core | 470 | 2.23 | 36.86 m | −1.2% | VISION_INERT (drift) |
| Town02 dense_near_r7_core | 1065 | 2.23 | 36.45 m | +0.1% | VISION_INERT (drift) |
| Town05 dense_slow_r7_core | 3100 | 1.67 | 44.18 m | −0.7% | VISION_INERT (drift) |
| Town10HD dense_slow_r7_core | 2587 | 2.24 | 36.91 m | −1.2% | VISION_INERT (drift) |
| Town06 R6 core (boundary) | 3681 | 2.23 | 36.99 m | −0.5% | VISION_INERT (confirmed) |
| Town07 R6 core (boundary) | 149 | 2.21 | 34.91 m | 0.0% | VISION_INERT (confirmed) |

---

## Recommended Options (user decision required)

### Option A — Re-record with autopilot on Town01 + Town10HD (recommended)

Record `dynamic_v3r7` cores with `--drive-mode autopilot` for Town01 and Town10HD.

- Pro: directly compares to the one positive result (dense_b1, autopilot); could replicate or refute the −14.3% signal under the R7 NPC recipe (`--npc-skip-ego-lane`)
- Pro: if Town10HD also shows VISION_ACTIVE under autopilot, we have 2-town evidence
- Con: 2 more recordings + 2 more VINS smoke + vision sensitivity = ~3 more hours
- Con: autopilot may block ego on Town01/10HD (was why gentle_turn was adopted) — needs preflight check

**Key question Option A answers:** Is the −14.3% signal reproducible under the R7 NPC recipe if we restore autopilot? Or was it NPC-on-ego-lane specific?

### Option B — Accept limited scope, revise paper claim

Accept that the positive signal (Town01 dense_b1) is recipe-specific. The VINS localization claim is:

> *"Under degraded IMU (industrial_fog) and specific urban recording conditions (high near-object density, autopilot ego, NPCs on all lanes), dynamic object masking reduces VINS ATE by ~14%. This signal disappears when NPCs are excluded from the ego lane (`--npc-skip-ego-lane`), suggesting the corrupting features originate from NPCs directly in the forward camera frame."*

- Pro: honest, no additional experiments
- Con: weak localization claim (one recording condition, one town)
- Con: the "NPCs on ego lane" condition is not the safe deployment scenario

### Option C — Per OpenSpec failure gate: downgrade to planner/perception-facing validity

Declare the VINS localization contribution FAILED. Focus paper on:
1. Component-wise object-state validity (position/velocity/full-state)
2. Planner-facing validity interface
3. Honest null result for VINS: "masking does not improve VINS localization under safe NPC placement; the signal observed with NPCs on the ego lane is a lane-placement artifact, not an object-validity effect"

- Pro: honest, principled
- Pro: the planner-facing contribution stands independently
- Con: weaker paper for localization venues

---

## ⛔ STOP

Do not run Phase 4 (TCSV life gate) without explicit approval.

Await decision on Option A / B / C before proceeding.
