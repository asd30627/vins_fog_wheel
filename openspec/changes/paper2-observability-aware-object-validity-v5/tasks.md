# Tasks — paper2-observability-aware-object-validity-v5

> 全用現有資料；不碰 backend/factor/G3；不重錄。每 gate STOP-and-report。

## V5-G0 — Evidence + positioning
- [x] G0.1 `PAPER2_V4_TO_V5_EVIDENCE_MAP.md`（v4 做什麼/A2 為何不 promising/哪些結果支持 v5）
- [x] G0.2 `PAPER2_V5_LITERATURE_POSITIONING.md`（focused lit check，定位差異不追 "first"）
- [x] G0.3 OpenSpec change 建立 + `openspec validate --strict`

## V5-G1 — Validity labels + observability phase map (C1)
- [x] G1.1 `scripts/paper2_v5_build_validity_labels.py`（從 benchmark_all[_with_vins] 建 validity labels）→ `paper2_v5_object_validity_dataset.parquet/.csv` + `PAPER2_V5_VALIDITY_LABEL_REPORT.md`
- [x] G1.2 observability/validity phase map（distance×density×bearing-change×depth×yaw-lever×track-age → full/position-only/invalid/warning regime）
- [x] **G1 GATE**：三段式 validity regime 由資料浮現、可解釋 → 報告

## V5-G2 — Observability Validity Index (C2)
- [x] G2.1 `scripts/paper2_v5_observability_index.py`（OVI 幾何項 + 輕量 calibration）
- [x] G2.2 baselines：distance-only / depth-only / bearing-change-only / yaw-lever+range / OVI-rule / OVI+calibration / (v4 NOUE score)
- [x] G2.3 metrics：AUROC velocity_valid/invalid_velocity、F1、false-valid/false-refusal、per bin/density/town → `paper2_v5_ovi_scores.csv` + `PAPER2_V5_OVI_RESULTS.md`
- [x] **G2 GATE**：OVI 是否勝單因子 baseline（抓 invalid-velocity）→ 報告

## V5-G3 — Refusal-aware policy (C3)
- [x] G3.1 `scripts/paper2_v5_refusal_policy.py`（levels: full/position-only/invalid-vel/unobservable/warning）
- [x] G3.2 對照：no-policy / v4 NOUE policy / v5 OVI policy / v5 OVI+calibration
- [x] G3.3 metrics：overconfident-wrong-velocity、invalid-vel recall、valid retention、planner-usable、position-only/warning ratio、per-bin → `PAPER2_V5_REFUSAL_POLICY_RESULTS.md`
- [x] **G3 GATE**：是否降 overconfident-wrong-velocity 且 false-refusal 可控 → 報告

## V5-G4 — Object-consistency ego diagnostic (C4, optional 加分)
- [x] G4.1 `scripts/paper2_v5_object_consistency_ego_diagnostic.py`（offline；多物體 fake lateral velocity 一致性 vs VINS scale/feat/outlier）
- [x] G4.2 相關性分析 → `PAPER2_V5_OBJECT_CONSISTENCY_EGO_DIAGNOSTIC.md`（promising/weak/null 誠實）
- 限制：不回饋 VINS、不加 factor、不宣稱 localization improvement

## 彙整
- [x] Z1 `PAPER2_OBSERVABILITY_AWARE_V5_SUMMARY.md`（spec path + validate、為何轉 v5、與競品差異、phase map、OVI、validity labels、refusal 結果、ego diagnostic、是否足為期刊主軸、blocked、下一步）
- [ ] Z2 STOP，等使用者 design checkpoint（不自動進 backend / 不自動定稿主題）
