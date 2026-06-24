# Route C — Execution Status (handoff, updated 2026-06-24)

Branch `p1-reliability-v1`. GitHub backup: `origin git@github.com:asd30627/vins_fog_wheel.git` (push OK).
Full spec: `openspec/changes/route-c-motion-conditioned-aniso-cov/` (proposal/design/specs/tasks; `openspec validate` = valid).

## CURRENT PROGRESS — Phase 1 wheel-on baseline COMPLETE (trio + clean four); awaiting USER review before Phase 2

**BOTH baselines done** (gate binary 15a57897, pb1.0, fixedext, callback, DL cov OFF, wheel topic ON / wheel factor OFF, CARLA off, **machine isolated**, each rep full-verified per-seq GT length). RAW numbers only — UNJUDGED. NEXT = the user personally reviews both tables before Phase 2 instructions.

**trio N=3 wheel-on cov-OFF baseline:**

| seq | N=3 ATEs (m) | median | range % | flag |
|---|---|---|---|---|
| urban35-seoul | 60.739 / 60.739 / 60.739 | **60.739** | 0.00% | — |
| urban31-gangnam | 108.348 / 108.348 / 108.348 | **108.348** | 0.00% | — |
| urban36-seoul | 260.775 / 260.775 / 255.425 | **260.775** | 2.05% | — |

**clean-four wheel-on cov-OFF baseline (adaptive N; horizontal round-robin; isolated):**

| seq | N | ATEs (m) | median | range % | md5 | note |
|---|---|---|---|---|---|---|
| urban28-pankyo | 3 | 17.555483 ×3 | **17.555483** | 0.0000% | `7e9b6577` | bit-identical 3/3 |
| urban29-pankyo | 2 | 8.461941 ×2 | **8.461941** | 0.0000% | `365016c9` | bit-identical 2/2 |
| urban26-dongtan | 2 | 11.931483 ×2 | **11.931483** | 0.0000% | `b1a8237a` | bit-identical 2/2 |
| urban27-dongtan | 2 | 43.847749 ×2 | **43.847749** | 0.0000% | `25c6410f` | bit-identical 2/2 |

Adaptive-N rule: run 3, stay N=3 if range ≤2% (bit-identical) else top up to N=5. All four were bit-identical from the start → urban28 ran to N=3 (the flagged ~17% seq — NO spread under isolation), the other three stopped at N=2 (already exact); round 3 was cancelled by the user (re-running bit-identical seqs wastes machine time). RAW numbers only — UNJUDGED (user judges sufficiency / whether to proceed; NOT delegated).

**★ KEY CONCLUSION (now in design.md Decision 10) — nondeterminism root cause = shared-machine resource contention, NOT VINS.** Under full isolation (CARLA off + machine idle) the clean four are run-to-run **bit-identical** (3/3, 2/2 — incl. urban28 which Decision 9 flagged ~16–19 m / ~3–4% spread). The earlier wheel-on nondeterminism was CARLA/concurrent-load contention perturbing async-callback interleaving — **VINS itself is deterministic under isolation** (same input → bit-for-bit same output). Decision 9's "2/3 best, not eliminable" was measured with a residual contention source still present; it is now SUPERSEDED IN PART by Decision 10.
**★ Ambush #1 (do-no-harm "noise > signal") RESOLVED:** isolated baseline = 0% noise (exact md5 match, not median-over-noise) → the 6.1 do-no-harm gate keeps its original 1–2% reproducible-Δ resolution; no weakening needed. **HARD precondition: Phase 2 cov-ON MUST also run isolated (CARLA off, no concurrent load), or the contamination returns and this resolution is void.**

## DONE so far
- **632 m blowup root cause = fixedext harness bug** (a run without `USE_EXPLICIT_FIXEDEXT=1` silently used the base-template extrinsic). FIXED: default `USE_EXPLICIT_FIXEDEXT` 0→1, legacy path now ERROR-STOPS. commit **9209ba9**.
- **Nondeterminism conclusion**: 100% bit-identical is unreachable (C2 + no-CARLA reached only 2/3). DECISION: stop chasing it; use multi-rep + **median** + run-to-run spread (spec L101) as the anti-cherry-pick mechanism.
- **C2 wheel preload**: implemented as an OPT-IN mechanism (env `REL_WHEEL_PRELOAD`; unset → original callback). DEFAULT DORMANT; gates do NOT enable it. fail-hard (preload empty / FOG-ref-without-preload → exit 7). commit **7ba2765**, honestly labeled "only 2/3, not solved".
- **ONNX export**: 8 LOSO per-fold (`reliability_cov_aplus_F-<seq>.onnx`) + 1 deployment, in `dl_reliability_ws/onnx_aplus_framei/`.
- **golden parity**: C++ REL_COV_DUMP abc vs Python onnxruntime = **max|Δabc| = 0** (exact); 15-dim input fed correctly; deployed model == trained.
- **cov-ON pipeline**: brought up end-to-end (ONNX loads, `net=1` inference, no crash). N=1 ATE not a gate number.
- **OpenSpec map corrected**: commit **49a508d** (tasks.md checkboxes aligned to reality; 3.3 marked NOT-CLEANLY-VERIFIED honestly; design.md **Decision 9** records the C2/V2/determinism evolution).
- **provenance chain**: gate binary md5 **15a578979bff7fa1a22220a5a4326acb** ← commit **7ba2765**; rebuild is byte-identical (reproducible).

## KEY SETTINGS (a new session's CC MUST know)
- **gate binary md5 = 15a578979bff7fa1a22220a5a4326acb** (currently installed; ← commit 7ba2765).
- **The two arms differ ONLY by DL cov:**
  - wheel topic **ON** (both arms: `PUBLISH_WHEEL_TOPIC=1` + `REL_WHEEL_REFERENCE_ONLY=1`)
  - wheel factor **OFF** (`WHEEL_FACTOR_ENABLE`=0, parameters.cpp default; not set in yaml/scripts — both arms)
  - DL cov: **baseline OFF** (unset `REL_ANISO_INFO/RC_APLUS/REL_USE_LEARNED_MODEL/REL_ONNX_PATH/REL_FEATURE_RELIABILITY`) / **cov-ON ON** (set those + the seq's held-out fold ONNX)
- **pb1.0 is the locked standard** — do NOT use 3.0.
- **trio real lengths**: urban35 = 172.7 s / urban31 = 1014 s / urban36 = 352 s (all shorter than urban28's 1973 s).
- **Old trio baseline (60.74/108.35/260.77) is VOIDED**: measured WHEEL-OFF (binary 49d1613998c2, pb3.0). Cannot be the wheel-on cov-ON basis. (The new wheel-on N=3 medians above — 60.739/108.348/260.775 — happen to match, but are now measured wheel-on with the gate binary.)
- `scripts/phase1_baseline.sh`: full-check is now **per-seq GT-length adaptive** (vio_last ≥ gt_last − 10 s); NOT hardcoded 1970 s.
- **wheel topic ON by itself improves urban28 ATE 24%** (24.89→18.82); mechanism OPEN (design.md Decision 7).
- Scripts: `scripts/phase1_baseline.sh <SEQ> <N>` (clean baseline arm; now supports `REP_START` env for adaptive-N top-up — reruns only reps REP_START..N, reusing earlier reps), `scripts/phase1_trio_n3.sh` (trio driver), `scripts/phase1_clean_four.sh` (clean-four adaptive-N, sequential), `scripts/phase1_clean_four_rr.sh` (clean-four horizontal round-robin — the one actually used). cov-ON arm = same env + DL block (write a clean cov-ON script for Phase 2, drop `REL_COV_DUMP`).

## NEXT STEPS (gated — each step waits for the USER's judgment)
1. ~~User reviews trio raw table~~ DONE — trio ranges 0/0/2.05%, user judged noise low, took N=3 medians, proceed.
2. ~~clean four wheel-on baseline~~ DONE — adaptive N (urban28=3, others=2), all bit-identical under isolation (table above). urban28's earlier ~17% spread did NOT recur (root cause = contention, Decision 10).
3. **★ NEXT — USER personally reviews BOTH complete baselines (trio + clean four)** before giving Phase 2 instructions. CC does NOT proceed to cov-ON. (Do NOT touch cov-ON / ONNX / gate.)
4. **Phase 2: cov-ON (held-out fold) through gates 6.0 → 6.1 → 6.2.** Each gate: lay out the raw table, STOP, the USER judges win — never self-judge. **MUST run isolated (CARLA off, no concurrent load) — Decision 10 precondition; else determinism/do-no-harm resolution void.** cov-ON arm = same env + DL block (write a clean cov-ON script, drop `REL_COV_DUMP`).

## AMBUSHES (status)
1. ~~**do-no-harm contradiction (noise > signal)**~~ **RESOLVED (Decision 10).** Isolated clean baseline is bit-identical (0% noise, exact md5) → 6.1 keeps the 1–2% reproducible-Δ resolution; no weakening. CONDITION: Phase 2 cov-ON must also be isolated, or the noise returns and this is void.
2. **STILL OPEN — "win = pure DL effect" assumption is unverified**: relies on "the wheel-topic 24% cancels between the two arms", but that cancellation (OPEN mechanism) was never verified. A reviewer may challenge this; task 6.0 (cancellation-cleanliness) is the partial check.

## IRON RULES (always)
- ATE → RAW TABLE ONLY (N values + median + range%). NEVER self-judge win / baseline-stability / "good enough".
- N count / gate pass-fail / baseline sufficiency = **USER judges, not delegated**.
- **win gate**: corruption trio ≥5% median ATE reduction AND all 3 reduce (consistent direction); ATE for any gate seq comes ONLY from its LOSO held-out fold (deployment model NEVER a gate number).
- Do NOT touch cov-ON / gates until the baseline is built and the user has seen the noise.
- **Actively check `pgrep`/files** — monitors get torn down at session boundaries; do not just wait for notifications.
- On any surprise needing a judgment: STOP, write it into this file, wait for the user. (History: the INVALID 33.73 self-declared "win".)

## Commits (fwvio repo, recent)
**c34769b** clean-four baseline DONE (isolated, bit-identical) + Decision 10 (determinism root cause = contention) · **9209ba9** fixedext fix · **49a508d** openspec map correction + Decision 9 · **7ba2765** C2 opt-in (dormant) + diagnostic scripts · (gate binary 15a57897 ← 7ba2765).
