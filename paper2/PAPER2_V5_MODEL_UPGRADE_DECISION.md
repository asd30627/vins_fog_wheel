# PAPER2 v5 — MODEL UPGRADE DECISION (2026-06-30)

> 從「OVI/refusal policy」升級為 **Selective Object State Validity Network** 的決策。**全程誠實、不包裝、壞結果照寫。** 紅線守住（未碰 backend/factor/G3、未重錄 CARLA、C4 已放棄/appendix）。

## 直接回答 5 問

### Q1. CARLA 是否有 collision / near-contact 污染？
**幾乎沒有。**（`PAPER2_CARLA_COLLISION_AUDIT.md`，24 runs）
- 整體 near-contact frame ratio = **3.8%**（物件層級 8.4%）。多數 run min front range > 5m；少數 ~3-4m = **近跟車（car-following），非碰撞**（基本無 <2m frames、極少 hard-brake）。
- 你看影片像「撞前車」，實際是**密集車流近距跟車**，不是碰撞事件。

### Q2. 過濾後 C1/C3 是否仍成立？
**仍成立、且幾乎不變。** 排除 near-contact 偵測後：velocity_valid by bin = 0.38/0.16/0.07（**與未過濾完全相同**），position_valid 近距**略升**（0.89→0.92, 0.73→0.76，移除難的近距重疊物）。→ 現象**不是碰撞 artifact**，robust。

### Q3. selective validity model 是否贏 distance gate？
**贏，明確。**（`PAPER2_SELECTIVE_VALIDITY_RESULTS.md`，velocity_valid AUROC，HistGBM）

| scenario | distance_gate | selective (HistGBM) | Δ |
|---|---|---|---|
| CARLA→CARLA (run split) | 0.755 | **0.873** | **+0.117** |
| KITTI→KITTI (seq split) | 0.686 | **0.919** | **+0.233** |
| CARLA+KITtrain→held-out-KITTI | 0.686 | **0.906** | **+0.220** |
| CARLA→KITTI (direct transfer) | 0.713 | 0.747(logistic) / 0.700(gbm) | +0.034 / −0.013 |

- **關鍵歸因（temporal ablation，誠實）**：增益由**時序一致性特徵**驅動，非幾何/距離。
  CARLA→CARLA: distance 0.755, **GEO-only 0.723（比 distance 還差）, TEMP-only 0.806, GEO+TEMP 0.864**；KITTI 同向（TEMP-only 0.879 > GEO-only 0.814 > distance 0.686）。
- **新訊號 = raw 估計的 runtime 可信度/穩定度**（raw_speed 是否物理不合理、raw_accel/vel_smooth 是否 frame-to-frame 跳動）→ 不需 GT 即可觀測，且**超越距離**。這是非顯而易見的方法洞見（一般會以為 validity 由距離決定，實際上「估計自身的時序不穩定」更具預測力）。
- **無洩漏**：所有 feature 為 runtime-observable；只有 label（vel_err≤3）用 GT。
- **誠實 caveat**：跨資料集**直接**遷移（CARLA→KITTI）弱（+0.034，HistGBM 跨域 overfit 到 0.700）→ 模型需少量 target-domain 資料校準（CARLA+KITtrain→held-out = +0.220 才強）。

### Q4. v5 是否能從 observation paper 升級成 model paper？
**能。** 因為 selective validity network 在嚴格 split（CARLA by run / KITTI by sequence，非 frame random）下**確實贏 distance gate 與 OVI**，且增益來自一個**可解釋、可部署、非顯而易見的訊號（raw 估計的時序一致性）**。這超出「只是描述現象」。

**升級後 v5 三大貢獻：**
1. **CARLA+KITTI dynamic-object velocity-validity 現象**（真實資料驗證、threshold-robust 27/27、near-contact-robust）：velocity 隨幾何崩潰、position 較穩、position-only regime 真實存在。
2. **Selective Object State Validity Network**：學習式 selective validity，**贏 distance/OVI baseline**，核心洞見 = **temporal-consistency of the raw estimate** 是比距離更強的 runtime validity 訊號。
3. **Refusal-aware state policy**：full-state / position-only / invalid-velocity / unobservable / warning，decision-level 評估（overconfident-wrong-velocity、false-refusal、planner-usable）。

### Q5. 若不能，是否該換方向？
**不需換方向。** 模型贏了 baseline，方向成立。（若當初連 temporal 特徵都不贏，我會建議降為純 measurement paper 或換方向——但實測贏了。）

---

## 我的誠實意見（你問了，且你也不滿意貢獻）
- **這次升級是真的，不是包裝。** 關鍵在於我沒有繼續硬推 OVI（它確實 marginal），而是換成「**raw 估計的時序自洽性**」這個之前沒測的槓桿——它在兩個資料集都贏 distance，且機制清楚（不穩的估計 = 不可信）。這把 v5 從「observation」推到「observation + method」。
- **但要誠實看待強度**：(a) 跨域直接遷移弱，需 target 校準；(b) KITTI 用 monocular depth（image_03 zip 曾損壞，已用 aria2c 重抓 ~95%，可做 stereo redo 更乾淨）；(c) velocity GT 來自差分（noisy）；(d) overconfidence 絕對值仍高（velocity 本質難）。這些是 mid-tier 可接受的限制，但 reviewer 會問。
- **這夠不夠？** 以 **mid-tier（IEEE IV / ITSC / RA-L / T-IV）** 而言，「真實資料驗證的現象 + 贏 baseline 的 selective model + temporal-consistency 洞見 + decision-level 評估」是**站得住的一篇**。要衝更高需再補：stereo KITTI、feature-importance/SHAP 把 temporal 故事釘死、第三資料集或更強跨域泛化、與 Qiu 2018 的並列實驗對照。
- **與 Qiu 2018 的差異現在更強**：他們用**幾何 observability 門檻**做 binary 拒絕；我們**實證顯示幾何/距離不是最強訊號、temporal-consistency 才是**，並用 learned multi-class validity + decision-level 評估 + 真實資料。這是實質方法差異，不只是換包裝。

---

## 建議下一步（不急著寫初稿，交你決定）
1. **（高價值）stereo KITTI redo**：image_03 已用 aria2c 重抓（~95%，初段極快、S3 尾段限速）。完成 + `unzip -t` 通過後，把 KITTI 改回 stereo depth → 與 CARLA 真正 apples-to-apples + 更乾淨的 velocity（去除 monocular class-height prior）。
2. **feature-importance / SHAP**：把「temporal-consistency 是主訊號」釘死（permutation importance 已由 ablation 佐證，SHAP 更直觀）。
3. **per-regime / failure gallery**：car-following / lateral-crossing / occlusion 分層。
4. 之後才起草（Intro/Related[Qiu 對照]/現象[C1+KITTI]/selective model[temporal 洞見]/refusal policy）。

## 產物
- `PAPER2_CARLA_COLLISION_AUDIT.md` + `paper2_carla_nearcontact_frames.csv`
- `scripts/paper2_carla_collision_audit.py`、`scripts/paper2_train_selective_validity.py`、`scripts/paper2_kitti_tracking_validity.py`(擴充時序特徵)
- `PAPER2_SELECTIVE_VALIDITY_RESULTS.md`(+temporal ablation) + `paper2_selective_validity_metrics.csv`
- `paper2_kitti_validity_dataset.csv`(37022, 21 seqs, 含 raw 位置/時序特徵)
- 本檔。

**STOP — 模型升級驗證完成（selective model 贏 distance gate，由 temporal-consistency 驅動，CARLA+KITTI）。未起草初稿。等你決定：stereo redo？SHAP？開始寫稿？**
