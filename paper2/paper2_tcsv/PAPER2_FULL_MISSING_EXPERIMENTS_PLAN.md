# PAPER2 — FULL MISSING EXPERIMENTS PLAN (P0 / P1 / P2)

> Comprehensive gap list to make **"Temporal-Consistency-Aware Selective Object State Validity for GPS-Denied
> Navigation"** journal-ready. Status reflects what was actually run in this round (Part C/D). Honest: items
> marked DONE were executed and produced artifacts; everything else is open.
> Hard boundaries (unchanged): topic fixed; no frontier/trajectory-planning main contribution (Paper-3);
> no VINS backend / object factor / localization claim.

Legend: **DONE** (run this round) · **PARTIAL** (started, gaps remain) · **TODO** (not started).

---

## P0 — 不補不能投 (blocks submission)

| # | item | status | what exists now | remaining |
|---|---|---|---|---|
| P0-1 | **CARLA grouping fix in ALL old reports** | PARTIAL | fix is live in `paper2_tcsv_features.py` (`(town,run,track_id)`); new reports use it; `PAPER2_TCSV_STORY_UPDATE.md` documents 0.873→0.800 | edit `PAPER2_SELECTIVE_VALIDITY_RESULTS.md` (CARLA +0.117→~+0.045) and any other doc quoting 0.873 |
| P0-2 | **threshold robustness after grouping fix** | DONE | `PAPER2_THRESHOLD_ROBUSTNESS_REGROUPED.md`: C1 14/18 combos (fails only at loose vel_t=5, expected), TCSV beats distance 6/6 vel_t settings | optionally add dir-threshold sweep for parity with old 27/27 |
| P0-3 | **leakage audit / feature provenance** | DONE | `PAPER2_LEAKAGE_AUDIT.md`: 14-feature provenance table; max single-feat AUROC 0.827; shuffled-label≈0.5; no feature∩GT cols | freeze feature list; restate in paper §V |
| P0-4 | **public/proxy baselines** | DONE | `PAPER2_PUBLIC_PROXY_BASELINE_RESULTS.md`: no_policy/distance/qiu-proxy/yolo-conf/bbox-depth/cv-smoothing/selectivenet-proxy/ovi + 3 TCSV × 6 splits × 8 metrics | (P1) upgrade selectivenet_proxy → real joint-trained SelectiveNet (needs torch); verify qiu-proxy against Qiu 2018 |
| P0-5 | **stereo KITTI redo** | TODO | monocular bbox-height depth in use; image_03 re-download ~95% | finish download, `unzip -t`, rebuild KITTI dataset, rerun TCSV + baselines + calibration |
| P0-6 | **Qiu 2018 claim-boundary table** | TODO | qiu_style(proxy) implemented; provenance clearly labeled "not the original" | read Qiu 2018 carefully; build the boundary table; ensure no "first observability gate" overclaim |

**P0 honest status:** 4 of 6 DONE this round (P0-2,3,4 fully; baselines complete). **P0-1 nearly done** (one-line edits left).
**P0-5 (stereo) and P0-6 (Qiu table) remain the two true blockers.**

---

## P1 — 補了才像期刊 (raises to journal quality)

| # | item | status | what exists now | remaining |
|---|---|---|---|---|
| P1-1 | **planner-facing TTC/risk minimal eval** | PARTIAL(DONE for CARLA) | `PAPER2_PLANNER_TTC_RESULTS.md`: CARLA front-object TTC; overconf-accepted 0.214→0.156 @cov0.8, false_alarm 0.200→0.140 | KITTI TTC (needs GT range); position-only TTC fallback variant |
| P1-2 | **failure gallery** | PARTIAL | `PAPER2_FAILURE_GALLERY.md`: data-driven per-regime metrics; position-only/far/occlusion populated | attach representative frames `[TODO]`; CARLA lateral-crossing too sparse (n=9) — widen criterion or drop |
| P1-3 | **SHAP / permutation importance figure** | PARTIAL | permutation importance done (`paper2_tcsv_importance.csv`); raw_speed dominant, KITTI cv_residual rank2 | SHAP needs `pip install shap`; make F4/F5 plots |
| P1-4 | **risk-coverage figure cleanup** | PARTIAL | `figs/fig_tcsv_riskcov.png` exists | overlay baselines #3–7; publication styling |
| P1-5 | **calibration / reliability diagram** | DONE | `PAPER2_CALIBRATION_RESULTS.md` + `figs/fig_tcsv_reliability.png`: raw ECE 0.02–0.03 (already well-calibrated); post-hoc Platt/isotonic does NOT help | report as-is (honest: raw is fine) |
| P1-6 | **cross-domain transfer expansion** | DONE | baselines cover CARLA→KITTI, KITTI→CARLA, CARLA+KITtrain→held-out-KITTI, +→held-out-CARLA | analyze: direct transfer weak; cv_smoothing transfers best; mixed-train recovers |

**P1 honest status:** calibration + cross-domain DONE; planner-TTC + failure-gallery + importance are PARTIAL (CARLA-side or numeric done, figures/extensions left).

---

## P2 — 加分項 (nice-to-have / rebuttal ammo)

| # | item | status | note |
|---|---|---|---|
| P2-1 | runtime / latency table | TODO | feature compute + inference latency per frame; trivially fast (sklearn), but measure |
| P2-2 | third dataset feasibility check | TODO | nuScenes / Waymo tracking feasibility (label availability for ego-independent vel) |
| P2-3 | per-regime analysis (car-following / lateral / occlusion / far) | PARTIAL | started in `PAPER2_FAILURE_GALLERY.md`; deepen with risk-coverage per regime |
| P2-4 | bootstrap confidence intervals | TODO | bootstrap over runs/sequences for AURC / overconf@ret CIs |
| P2-5 | ablation on thresholds & operating retention | PARTIAL | overconf@ret.8/.9 reported; add full retention sweep + threshold sensitivity |

---

## Recommended execution order (highest leverage first)
1. **P0-1** (10-min edits) — remove the stale 0.873 from old reports; consistency.
2. **P0-6 Qiu table** + verify qiu-proxy — protects the central novelty claim, cheap.
3. **P0-5 stereo KITTI redo** — biggest data-quality lever; will shift numbers; do before freezing.
4. **P1-3/P1-4** figures (SHAP + risk-coverage) — make the temporal-consistency story legible.
5. **P1-1 KITTI TTC + position-only fallback** — strengthens C3.

## Discipline notes
- Do NOT re-tune thresholds or re-pick sequences to inflate numbers (gated-execution discipline).
- Do NOT add experiments outside this list; frontier/trajectory planning → Paper-3.
- Keep every proxy labeled as a proxy; never claim equality with an original method.
- cv_smoothing_gate is a strong honest baseline — keep it prominent, do not bury it.
