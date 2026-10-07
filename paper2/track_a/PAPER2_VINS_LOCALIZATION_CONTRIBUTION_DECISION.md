# PAPER2 — VINS LOCALIZATION CONTRIBUTION DECISION (final)

> Can Paper-2's validity model claim a VINS/VIO localization improvement? Honest synthesis after the
> data-quality clean-up. Date 2026-07-01. Evidence: all Phase -1..1 + Phase 3/4/5 design/feasibility docs,
> PAPER2_VALIDITY_AWARE_VINS_{RESULTS,DECISION}.md (prior run, now re-scoped to clean data only).

## Status of the VINS experiments after clean-up
- Valid evidence exists on **only 2 clean+stable runs** (Town01 dense_b1, medium_b1). Town06 (unstable
  baseline) = failure-analysis; Town07 (invalid spawn collision) = dropped.
- On those 2 clean runs: dynamic-object feature suppression gave **−10.5% / −2.8% ATE, 0 VINS failures**, with
  deployable gate ≈ all_dynamic ≈ oracle. Small, consistent, no regression — but **n=2 is far too few to claim**.
- Phase 2 (real TCSV-M masking) tooling is designed; **execution is GATED** on expanding the clean-data set
  (re-record needs the additional fixes in the data-quality decision). Running it on 2 runs would not be
  conclusive.

## Answers to the 10 questions
1. **Raw CARLA spawn/visibility problems?** Yes — global-spawn placement + spawn collision (see data-quality decision).
2. **Runs excluded / re-recorded?** 17 INVALID excluded; queued for re-record (not yet done — preview failed).
3. **Re-recorded data passes gate?** Not yet — spawn-placement fix is necessary but insufficient; deeper fixes pending.
4. **Does TCSV-M improve VINS?** **Unproven.** Not yet tested with the real TCSV-M on sufficient clean data. The
   prior positive signal used a raw-speed gate on only 2 clean runs.
5. **Improvement from TCSV-M or from crude dynamic removal?** On clean runs the deployable gate ≈ all_dynamic
   ≈ oracle → the improvement (where present) is from **removing dynamic features at all**, not from the
   sophistication of the validity signal. TCSV-M has NOT been shown to add value over crude removal.
6. **Better than raw_speed / cv_smoothing / all_dynamic?** Not demonstrated. On the 2 clean runs the variants
   are within ~1% of each other. Needs TCSV-M + more clean runs to answer.
7. **Approach oracle?** On the 2 clean runs yes (all variants ≈ oracle, differences within noise); on degraded/
   invalid runs only oracle was safe — but those runs are excluded now.
8. **Claim localization improvement in the Paper-2 main text?** **No.** Evidence is insufficient (n=2 clean
   runs, real model untested, dominant error is IMU scale-drift not dynamic pollution). Claiming it would be
   over-reaching.
9. **Appendix / secondary evidence instead?** **Yes** — the honest position: report as a **bounded secondary
   finding** ("on clean, stable-baseline sequences, suppressing dynamic-object features yields a small ATE
   improvement with no added failures; a deployable validity gate matches naive all-dynamic removal and
   approaches the GT oracle; perfect-knowledge upper bound ≈ −17%"). Keep Paper-2's headline
   planner/perception-facing (Part 1 selective validity).
10. **To make it Paper-3, what's still needed?** (a) Fixed + expanded clean recordings (autopilot-delay
    re-record; or nuScenes, downloading now); (b) real TCSV-M masking + feature-level routing (Phase 3) with
    per-object feature counts; (c) soft covariance weighting (Phase 4) for robustness; (d) curb the IMU
    scale-drift so dynamic pollution becomes the leading error; (e) many sequences with bootstrap CIs; (f)
    only if soft weighting reliably ≥ all_dynamic and ≈ oracle, consider a dynamic-object motion factor
    (Phase 5a). Learning-through-BA (Phase 5b) is NOT recommended (Ceres non-differentiable; low payoff).

## Fits the 國科會 GPS-denied / mapless theme?
Yes — robust VIO under dynamic traffic without GPS/HD-map is on-theme. But the claim must be scoped to the
honest evidence: a bounded improvement mechanism, not a solved localization result.

## One-paragraph verdict
After removing the data-quality confounds, the VINS-localization line has **only 2 clean stable runs of
evidence**, on which dynamic-feature suppression gives a small, safe, but **sophistication-agnostic** ATE
improvement (deployable ≈ naive ≈ oracle). This is **insufficient to claim a localization contribution in
Paper-2's main text.** Keep Paper-2 headline = Part-1 selective validity (planner/perception-facing); carry the
VINS result as a bounded appendix finding; pursue the full localization story as **Paper-3** only after fixing/
expanding the recordings, plugging in the real TCSV-M with feature-level routing + soft weighting, and curbing
the scale-drift that currently dominates the error.
