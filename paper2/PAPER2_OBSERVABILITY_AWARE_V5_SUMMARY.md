# PAPER2 OBSERVABILITY-AWARE v5 SUMMARY (2026-06-30)

> v5 = **Observability-Aware Dynamic Object State Validity for GPS-Denied Navigation**。全用現有 24-run dataset + benchmark + VINS replay，**未碰 backend、未加 object factor、未進 G3 scaffold、未重錄、未刪 v4、未過度 claim**。完成 spec + prototype + summary 後 STOP。

## 1. OpenSpec
- Path：`openspec/changes/paper2-observability-aware-object-validity-v5/`（proposal/design/tasks/spec）。
- `openspec validate paper2-observability-aware-object-validity-v5 --strict` → **valid**。5 個 change 並存（v5 + v4 + g0 + Paper-1 ×2），v4 結果保留。

## 2. 為什麼從 v4 轉 v5（見 `PAPER2_V4_TO_V5_EVIDENCE_MAP.md`）
- v4 核心賭注 A2（物體可信度 conditioned on VINS quality，feature concat）**經嚴格測試不成立**（sensor-frame FAILED、world-frame WEAK）。把定位品質當 feature 串接進 error-regression 冗餘且不穩。
- 但既有資料**強烈支持 observability/validity 切角**：velocity validity 隨距離崩潰、position 較緩、refusal 已證有效。→ 改成**幾何可解釋的 observability/validity 判準 + refusal**，而非 black-box feature conditioning。

## 3. 與 conformal risk tube 的差異（"PURI-DO" 不存在 — 實為 Fu & Chen, ICRA 2026 preprint, arXiv 2603.23919）
- 他們：risk-importance scoring + conformal coverage（哪個物體「重要/危險」）。我們：**geometric state observability / validity**（這個物體的 velocity 此刻能不能估）。不同問題、不同輸出、不同評估。**我們不以 conformal risk tube 為主創新。**

## 4. 與 dynamic SLAM / object-tracking 的差異
- VDO-SLAM / DynaSLAM II / ClusterVO / DOT-SLAM / DL-SLOT：**永遠輸出 object velocity（SE(3) 差分），從不 gate on observability**，只在 discussion 列失敗模式。→ 「they estimate-and-hope; we decide-then-(maybe)-estimate」。
- DynaVINS / IDY-VINS：剔除動態特徵保護 ego 定位（相反目標）。
- **最接近的威脅（必引、claim 必收窄）**：**Qiu et al., IROS 2018**（monocular VI 動態物體 metric pose + observability 條件，**在 4 種退化（相機跟車/靜止相機/等速相機/靜止物體）拒絕輸出 metric scale**）。→ **不能 claim「first 發現物體不可觀測 / first gate on observability」**。可守差異：(a) **road-geometry regime/phase map** vs 他們單一 scalar threshold；(b) **5-way refusal**（velocity-invalid vs position-only 分離）vs 他們 binary accept/keep-up-to-scale；(c) **decision-level evaluation**（invalid-vel recall/precision、overconfident-wrong、false-refusal）vs 他們 tracking accuracy。
- 理論祖先：bearings-only TMA（Nardone & Aidala 1981）= 「無 observer maneuver 則 velocity 不可觀測」，引為 foundation，不 claim 為新。

## 5. Observability/validity phase map (C1) — `PAPER2_V5_VALIDITY_LABEL_REPORT.md`
matched 物體 validity（n=15811，閾值可 ablation）：

| distance bin | n | pos_valid | **vel_valid** | position_only | invalid_vel |
|---|---|---|---|---|---|
| 0-15m | 1863 | 0.89 | **0.38** | 0.55 | 0.62 |
| 15-30m | 4164 | 0.73 | **0.16** | 0.61 | 0.84 |
| 30m+ | 9784 | 0.30 | **0.06** | 0.27 | 0.94 |

- **velocity validity 0.38→0.16→0.06**（連近距僅 38%）→ 「永遠輸出 velocity」是錯的。**三段式 regime（full-state / position-only / unobservable）由資料浮現。** position_only 是真實 regime。

## 6. Observability Validity Index (C2) — `PAPER2_V5_OVI_RESULTS.md`
**幾何可解釋**（非 black-box）：`log_range`、`yaw_lever=range·sin(yaw_sigma)`、`bearing_change_rate`、`depth_noise=disp_std/disp_med`、`vel_obs_proxy=bearing_change/range`、`track_stability`；logistic calibration（係數可檢視）。
- velocity-valid 偵測 AUROC：**OVI_calibrated 0.797 ≥ distance-only 0.790（overall）；within-bin mean 0.641 > 0.621**；最大 gain 在 **15-30m（0.809 vs 0.661）**。
- 主導項：`log_range`(−0.52) + `bearing_change_rate`(+0.60)（幾何合理：遠=不可觀測、bearing 變化大=velocity 可觀測）。
- 誠實：gain modest（velocity validity 本就強隨距離，distance 已抓粗相關）；OVI 的價值在 **within-regime 區辨 + 可解釋**，尤其 mid-range velocity 觀測性。

## 7. Validity label 定義（閾值可 ablation，非絕對）
`position_valid=pos_err≤3m`；`velocity_valid=speed_err≤3 且 dir_err≤45°`；`full_state=both`；`position_only=pos 但非 vel`；`invalid_velocity=非 vel`；`unobservable_candidate=invalid 且(低 bearing-change 或 遠 或 高 depth-jitter)`；`high_risk=invalid 且 近`。

## 8. Refusal policy 結果 (C3) — `PAPER2_V5_REFUSAL_POLICY_RESULTS.md`
| policy | emit_vel | overconfident_wrong_vel | invalid_recall | valid_retention | false_refusal |
|---|---|---|---|---|---|
| no_policy | 1.00 | **0.839** | 0.00 | 1.00 | 0.00 |
| distance(<15m) | 0.37 | 0.636 | 0.72 | 0.830 | 0.170 |
| **v5 OVI** | 0.40 | **0.640** | 0.69 | **0.904** | **0.096** |
- v5 OVI policy 把 overconfident-wrong-velocity **0.839→0.640**，且**比 naive distance 更好的 trade-off**（valid retention 0.904 vs 0.830、false-refusal 0.096 vs 0.170，同等 overconfidence）。level：full 0.40 / **position_only 0.38** / unobservable 0.20 / warning 0.02；planner-usable 0.785。
- 誠實 caveat：emitted 仍 64% 錯（velocity base invalid 0.84 太高）→ 印證「多數 velocity 本就不可觀測」；refusal 改善 trade-off，但無法救本質不可觀測的 velocity。v4 NOUE policy 參考值 0.586→0.387（不同 split，不可直比）。

## 9. Object-consistency ego diagnostic (C4, optional) — `PAPER2_V5_OBJECT_CONSISTENCY_EGO_DIAGNOSTIC.md`
- **NULL/weak**：per-frame 物體運動誤差 vs VINS outlier/feat 的 Spearman rho ≈ −0.05/−0.00（n=4377），rec-level 樣本不足。→ 物體運動不一致**在此資料無法當 independent ego-degradation alert**。**誠實標 null，不包裝。**（confound：物體速度誤差也被 range/observability 驅動；VINS 發散為 640 激進轉彎 artifact。）

## 10. 是否足夠成為期刊主軸（誠實）
- **強處**：velocity-unobservability 的資料證據紮實（vel_valid 0.38→0.06）；validity phase map（measurement）+ refusal policy（clean decision framing，Pareto 勝 naive distance）+ 可解釋 OVI；「decide-then-estimate vs estimate-and-hope」定位清楚。
- **弱處/限制**：Qiu 2018 已做 observability-gated object state → 新穎性**收窄為 regime-map + multi-class refusal + decision-level eval**；OVI gain modest；C4 null；資料限 Town10HD+Town01、raw velocity=centroid-diff（noisy）、VINS 發散 artifact。
- **判斷**：**足以成為一篇紮實的 measurement + methodology 論文（mid-tier：IEEE Sensors / IV / 收緊後或可 RA-L），非 breakthrough。** 主軸建議 = 「dynamic object state **validity/refusal** layer + road-geometry observability **phase map** + interpretable **OVI**」，claim 對 Qiu 2018 收窄、對 dynamic-SLAM 與 conformal-risk-tube 明確區隔。**不要 claim first observability；用 "to our knowledge / we focus on / unlike methods that…"。**

## 11. Blocked / 限制
- velocity GT = GT actor 速度；raw velocity = 跨 frame centroid diff（noisy）→ validity label 有噪，需閾值 ablation（2/3/5m、dir 30/45/60）。
- VINS scale 發散（640 激進轉彎 artifact）汙染 yaw_sigma proxy 與 C4。
- 資料 town 多樣性限 2（Town04/02 CARLA 不穩）；velocity 觀測性結論標 scope。
- 部分文獻 venue 標 [PARTIAL]（見 `PAPER2_V5_LITERATURE_POSITIONING.md`），引用前需逐一核對；勿引未驗證作者。

## 12. 下一步建議（交你 design checkpoint，不自決）
1. **收窄定稿主題**：對 Qiu 2018 寫明三點差異（regime-map / multi-class refusal / decision-eval）；validity phase map + refusal policy 當雙主貢獻，OVI 當可解釋方法、C4 當誠實 null/minor。
2. **強化 C1/C3**（最有力）：validity 閾值 ablation、per-regime（car-following / lateral-crossing / occlusion）細分、missed-danger 評估。
3. **OVI 擴充**：加 parallax/association-stability 項、per-class 校準；報 within-regime gain 為主指標。
4.（optional）若要救 velocity 絕對精度：更好的 raw velocity 估計（光流/RAFT 而非 centroid-diff）——但這偏 detector/tracker 改良，非 v5 主軸。
5. 維持紅線：不碰 backend、不加 object factor、不進 G3、不重錄（除非明確資料缺口 + 你批准）。

## 產物清單
- 報告：`PAPER2_V4_TO_V5_EVIDENCE_MAP.md`、`PAPER2_V5_LITERATURE_POSITIONING.md`、`PAPER2_V5_VALIDITY_LABEL_REPORT.md`、`PAPER2_V5_OVI_RESULTS.md`、`PAPER2_V5_REFUSAL_POLICY_RESULTS.md`、`PAPER2_V5_OBJECT_CONSISTENCY_EGO_DIAGNOSTIC.md`、本檔。
- 資料：`paper2_v5_object_validity_dataset.parquet/.csv`、`paper2_v5_validity_with_ovi.parquet`、`paper2_v5_ovi_scores.csv`。
- scripts：`paper2_v5_{build_validity_labels,observability_index,refusal_policy,object_consistency_ego_diagnostic}.py`。
- OpenSpec：`openspec/changes/paper2-observability-aware-object-validity-v5/`。

**STOP — v5 spec + prototype + summary 完成。未進 backend、未定稿主題。等你 design checkpoint。**
