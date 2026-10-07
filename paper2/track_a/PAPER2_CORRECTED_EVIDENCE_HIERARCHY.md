# Paper-2 — Corrected Evidence Hierarchy

**Date:** 2026-07-02 (audit pass)
**Basis:** `PAPER2_YESTERDAY_CLAIM_AUDIT.md` + 5 sub-audits.
**Principle:** a result's tier is set by what it can honestly defend, not by how much effort it took.

---

## Tier 1 — Main paper evidence (defensible headline)

| result | why Tier 1 | placement | caveat to state |
|--------|-----------|-----------|-----------------|
| **KITTI Mondrian OPL** (exceedance 0.1140 @IR=0.10, PASS; 21 scenes, leave-scene-out; beats scene-split & distance-gate) | Real data, proper cross-scene conformal protocol, baselines present, formal RAIM bound | **main text — headline** | exclude IR=0.20 (fails); availability 32.4%; per-scene spread is wide |

**That is the only unambiguous Tier-1 result.** The paper's spine is the obstacle-state integrity
(OPL) formalism on KITTI.

---

## Tier 2 — Supporting evidence (valid but limited)

| result | role | placement | caveat |
|--------|------|-----------|--------|
| Phase 4.2 closed-loop OPL benefit (near_coll −94%, 0 collisions) | shows the OPL bound drives a safe policy | main text, clearly labeled controlled 2D sim | GT pose, synthetic scan, 5 seeds |
| Phase 4.3 OPL≠LPL structural gap (false_safe≈255 all conditions) | motivates the dual-channel design | main text (motivation), sim | proof-of-concept, not statistical |
| nuScenes reliability replication (target-calib 0.969) | 3rd real dataset, structure replicates | ablation / supporting | zero-shot weak (0.69); needs target calibration; proxy pipeline |
| VINS raw-speed dynamic mask (−10.5% / −2.8% ATE, 2 clean CARLA runs) | localization-layer benefit exists | ablation | NOT learned PV; image blur; 2 runs; limited headroom |

---

## Tier 3 — Exploratory / appendix (smoke, feasibility, single-route)

| result | role | placement | caveat |
|--------|------|-----------|--------|
| HealthNet cross-grade transfer (LOGO AUROC 0.94–1.0, urban38 only) | entropy signal transfers across IMU grades of one route | appendix | single route; cross-route not evaluable; random-split ~1.0 is leaky |
| LPL isotonic v1 (CARLA, 0 HMI, 1.85% avail) | honest research-gap documentation | appendix / limitations | 1.85% availability = not deployable; scale-drift gap open |
| ORB-SLAM3 baseline + relay smoke | wrapper-approach portability | appendix (infra note) | no ATE; trajectory not obtainable without code change |
| acc-bias runtime detection (accbias_flag → UNAVAILABLE) | lightweight partial LPL signal | appendix | 1 real-sensor scene |

---

## Tier 4 — Remove from main paper

| result | why removed | disposition |
|--------|-------------|-------------|
| **Phase 4.4 dual-channel benchmark** | broken metric (collision% up to 6100%); table contradicts its own conclusion; n=3 | REMOVE; fold the single qualitative point into Phase 4.2 |
| **HealthNet "AUROC 0.963 / works" as a capability** | within-distribution, single-sequence, leaky, single-feature | REMOVE the capability framing; keep only the cross-grade micro-result in appendix |
| **HealthNet time-to-alert as early-warning** | TTA = 0s | REMOVE early-warning framing; it's a state detector |
| **ORB-SLAM3 PV-mask "localization improvement / promising"** | no ATE, no comparison | REMOVE any improvement language; keep as infra note |
| **"full paper-ready package complete"** | only Tier-1 B qualifies | REMOVE the completeness claim |
| **"validity_aware / PV mask" naming for VINS** | it's a raw-speed gate | RENAME (not remove) to "raw-speed dynamic mask" |

---

## One-paragraph honest summary of the package

> The defensible core is a **RAIM-style obstacle-state integrity (OPL) formalism**, calibrated by
> leave-scene-out conformal regression on KITTI (exceedance 0.1140 at IR=0.10, PASS), with a
> controlled-simulation closed-loop showing the bound yields a safer policy than naive or hard-stop,
> and a structural argument that OPL cannot cover localization degradation. Supporting evidence:
> the reliability structure replicates on nuScenes (with target calibration), and a raw-speed
> dynamic-object mask gives a small VINS ATE improvement on two clean CARLA runs. The
> localization-integrity (LPL) and learned-HealthNet directions are **honest research gaps**, not
> results: LPL availability is 1.85%, and HealthNet failures exist on only one route so cross-route
> generalization cannot be evaluated. ORB-SLAM3 masking is infrastructure only (no trajectory/ATE).
