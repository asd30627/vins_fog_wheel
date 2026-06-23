# Route C — Execution Status (handoff, updated 2026-06-24)

Branch `p1-reliability-v1`. GitHub backup: `origin git@github.com:asd30627/vins_fog_wheel.git` (push OK).
Full spec: `openspec/changes/route-c-motion-conditioned-aniso-cov/` (proposal/design/specs/tasks; `openspec validate` = valid).

## CURRENT PROGRESS — Phase 1 wheel-on baseline IN PROGRESS

**trio N=3 wheel-on cov-OFF baseline DONE** (gate binary 15a57897, pb1.0, fixedext, callback, CARLA off, isolated, each rep full-verified per-seq GT length):

| seq | N=3 ATEs (m) | median | range % | flag |
|---|---|---|---|---|
| urban35-seoul | 60.739 / 60.739 / 60.739 | **60.739** | 0.00% | — |
| urban31-gangnam | 108.348 / 108.348 / 108.348 | **108.348** | 0.00% | — |
| urban36-seoul | 260.775 / 260.775 / 255.425 | **260.775** | 2.05% | — |

All ranges < 5% → no escalation flags raised. RAW numbers only — UNJUDGED (the user judges baseline stability / whether to add N / whether to proceed; NOT delegated).
Note (observation, not judgment): urban35 & urban31 were bit-identical run-to-run (3/3 same md5); urban36 rep3 differed (range 2.05%). The wheel-on run-to-run nondeterminism seen earlier appears urban28-specific (~17%), not universal.

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
- Scripts: `scripts/phase1_baseline.sh <SEQ> <N>` (clean baseline arm), `scripts/phase1_trio_n3.sh` (trio driver). cov-ON arm = same env + DL block (write a clean cov-ON script for Phase 2, drop `REL_COV_DUMP`).

## NEXT STEPS (gated — each step waits for the USER's judgment)
1. **User reviews the trio raw table** → judges noise magnitude (any seq with range >5% gets N=5; >15% needs special handling). [trio ranges were 0/0/2.05% — all <5%.]
2. **clean four (urban28/29/26/27) wheel-on baseline, N=5** (do-no-harm gate threshold is tight). Use `phase1_baseline.sh <seq> 5`. NOTE urban28 had ~17% run-to-run spread earlier — watch it.
3. **Phase 2: cov-ON (held-out fold) through gates 6.0 → 6.1 → 6.2.** Each gate: lay out the raw table, STOP, the USER judges win — never self-judge.

## TWO AMBUSHES AHEAD (know in advance)
1. **do-no-harm contradiction**: clean sequences may carry run-to-run noise larger than the 1–2% degradation 6.1 must detect (noise > signal). Face it at 6.1; the do-no-harm standard may need reproducible-Δ language.
2. **"win = pure DL effect" assumption is unverified**: it relies on "the wheel-topic 24% cancels between the two arms", but that cancellation (the OPEN mechanism) was never verified. A reviewer may challenge this; task 6.0 (cancellation-cleanliness) is the partial check.

## IRON RULES (always)
- ATE → RAW TABLE ONLY (N values + median + range%). NEVER self-judge win / baseline-stability / "good enough".
- N count / gate pass-fail / baseline sufficiency = **USER judges, not delegated**.
- **win gate**: corruption trio ≥5% median ATE reduction AND all 3 reduce (consistent direction); ATE for any gate seq comes ONLY from its LOSO held-out fold (deployment model NEVER a gate number).
- Do NOT touch cov-ON / gates until the baseline is built and the user has seen the noise.
- **Actively check `pgrep`/files** — monitors get torn down at session boundaries; do not just wait for notifications.
- On any surprise needing a judgment: STOP, write it into this file, wait for the user. (History: the INVALID 33.73 self-declared "win".)

## Commits (fwvio repo, recent)
**9209ba9** fixedext fix · **49a508d** openspec map correction + Decision 9 · **7ba2765** C2 opt-in (dormant) + diagnostic scripts · (gate binary 15a57897 ← 7ba2765).
