# ORB-SLAM3 專案盤點 — v1（2026-07-13）

> 承接 `openspec_shared_object_memory_orbslam_frontier_v3.md`（2026-07-02）的 Topic A 稽核，統整自該日起到 2026-07-13 為止，`shared_object_persistence_orbslam_frontier_ws/src` repo（branch `5090`, HEAD `f36a7c9a` 2026-07-04）之上所有 ORB-SLAM3 相關實驗分支的現況。本 repo 的主 estimator 依然是 VINS-Fusion（`fwvio_estimator_ws_wheel`），ORB-SLAM3 是這條 repo 上獨立生長出的一系列研究支線，**與 v3 文件描述的 `~/orbslam_ws` 獨立 workspace 不是同一份程式碼**——真正被改動的 ORB-SLAM3 核心其實是 vendor 進本 repo 的 `external/orbslam_ws/src/orb-slam3-ros2/orbslam3_core/`，`5090` 分支本身沒有這份程式碼，是各實驗分支各自從 `5090` 岔出後才引入/修改。

## 0. 結構性事實（先講地基，不講故事）

- **`5090` 主分支自 2026-07-04（`f36a7c9a`）後未再前進**——之後列出的每一條分支全部是從這個共同祖先各自岔出，彼此互不相通，沒有合併回主線。這代表「ORB-SLAM3 這邊做了什麼」目前**不是一條累積式的開發線，而是 20+ 條互相獨立的探索分支**，多數是 gate 型（單一問題 PASS/FAIL 就結束）而非持續疊代的 feature 分支。
- **除 `p2-a-evidence-gated-semantic-slam-spec` 外，全部未推送到 origin。** 也就是說除了那一條，其餘實驗歷史目前只存在本機。
- `P2AGate.h`/`P2AGate.cc`（P2A 系列開發出的 ORB-SLAM3 keypoint 抑制 gate）存在於：`p2-a-evidence-gated-semantic-slam-spec`、`spectra-landmark-lifecycle`、`d1-g0-persistence-existence`、`d1-g1-starvation-shadow`、`d2-g1-attribution-change`、`p05-g1-runtime-reloc-logging` 這幾條下游分支，但**未合併回 `5090`**。

## 1. Direction A — Evidence-Gated Semantic SLAM（P2A 系列，2026-07-07～09，已收斂）

分支 `p2-a-evidence-gated-semantic-slam-spec`（唯一已推送），HEAD `f79d9490`（2026-07-09）。目標：per-frame object evidence 即時抑制/放行 ORB-SLAM3 前端的 keypoint/MapPoint，取代粗粒度的動態物體全域遮罩。

**執行順序（P2A-0 → P2A-2l）與結論**（詳見 memory `project_p2a_evidence_gated_slam_pivot.md`，此處只列終局狀態）：

- P2A-0/0b：早期 per-frame 特徵（bbox 幾何、keypoint-MapPoint 關聯）確認存在且 schema 一致 → G0 PASS。
- P2A-1/1b/1c：早期特徵預測未來 MapPoint 關聯的可學習性，修正兩次 label 設計後拿到**第一個正結果**（GBT AUPRC +0.22~0.49，嚴格 family-split 存活），完成離線 gate 校準與 suppress/neutral/boost 決策政策。
- P2A-2 系列（a→l，含兩次 Fable 稽核）：把 gate 真正接進 ORB-SLAM3（`Frame::ExtractORB` 後過濾），修過一次 build 阻塞、一次 mnId→timestamp 對齊 bug、一次 harmful-target 重新定義（從「未來不會被關聯」改成「移動中且未來仍被關聯＝真正有害」）。最終 LEVEL 1-4 全部跑完：suppress-only smoke 在兩條 CARLA 序列上實際/預測移除比 1.00×~1.10×，GBDT 在 leave-one-family-out 上打贏所有規則 baseline（AUROC 0.931 vs 0.832）。
- **狀態：離線信號成立、線上 gate 機制驗證可安全運作，但尚未跑到 P2A-3（真正的 ATE/RPE SLAM 準確度評估）就停在這個分支上**——沒有更晚的 commit，本次稽核確認 HEAD 未超出既有 memory 記錄範圍。

## 2. C2 — Observation Lifecycle（4-class SLAM 路由，2026-07-10，NEGATIVE 收尾）

`c2-s2-lifecycle-backend-spike` → `c2-s3a` → `c2-s3b-lite` → `c2-s3c` → `c2-s3d-runtime-cap-fair-rerun`（全部未推送，全部 2026-07-10 當天完成）。

目標：把每個 per-frame 物體觀測路由成 PERSISTENT_MAP / EPHEMERAL_TRACKING / DOWNWEIGHT / REJECT 四類，取代 P2A 的二元 suppress/boost。

- S2 spike 實作 Option C（阻擋 Atlas 註冊）、S3a 修正三個 coverage/leak 路徑（含一個 KeyFrame 建構子整批複製 `Frame::mvpMapPoints` 造成的洩漏，S2 沒抓到）。
- S3b-lite 26 次 replay 全部乾淨（0 crash/leak），但 D 方案 ATE 輸給 B/E（~8m vs ~0.5m）——**負訊號，且損害發生在 pose-optimization 階段，不是 persistent-map 階段**。
- S3c 一度以為找回訊號（EPH 方案打贏 E），但 S3d 用真正公平的 C++ runtime timeout 重跑後推翻：**S3c 的「贏過 E」是計時比較口徑不公平造成的假象**，真正公平重跑下 EPH 機制本身在 5/10/15/20% cap 全部機制正確，但 ATE 零改善，仍匹配未設限的 D（8.7-9.0m），不是 E（0.6m）。
- **狀態：`C2_S3D_FAIL`，整條線收斂為負結果**。已寫出但**未核准/未執行**的 S4x（layer-vs-survivor-selection 混淆隔離實驗）是唯一還開著的後續分支，停在規劃階段。

## 3. XT-G 系列 — 跨光譜（Thermal/RGB）地圖重定位（2026-07-11～12）

一組平行分支，主題是「白天 RGB 建圖、夜間熱像儀重定位」，比 P2A/C2 更接近方法論探索而非單一 gate。

| 分支 | 日期 | 結論 |
|---|---|---|
| xt-g0-thermal-matching | 07-11 | **GO**：day-RGB map → night-thermal cross-spectral relocalization 在 MS² 資料集上初步可行 |
| xt-g1b-strong-baselines-map-relocalization | 07-11 | 研究定案：offset 問題根因為 KF-anchoring（非資料/演算法本身），XSPR-v1 方法固化提交 |
| xt-g2-xspr-training | 07-11 | **KILL**：所有 baseline 中 MegaLoc 表現最強（TEST R@10=0.96），學習式 XSPR 未能超越 |
| xt-g3-thermal-query-geometry | 07-11 | **REFORMULATE**：thermal query-side 幾何 gate 方向需要重新設計 |
| xt-g4-parallax-decoupled | 07-11 | CS-Verify 訓練模組 + frozen transfer **PASS**，研究包完成 |
| xt-g4-opus-engineering | 07-12 | 方法凍結：改採 Parallax-Decoupled Alignment (PDA)，核心假說仍未證實；W1 warp-observability pilot **INCONCLUSIVE**（機制混淆，非特徵層面結論） |

補充脈絡（見 memory `project_xtg1b_map_relocalization_20260711.md`、`project_xtg4_*`、`reference_nsavp_20260712.md`、`reference_vivid_access_20260712.md`）：這條線的瓶頸反覆定位在「跨模態檢索/驗證」而非匹配或深度本身；ViViD++ 外部資料集因存取限制（.edu email + KAIST 伺服器 403）未能取得，轉而使用 NSAVP。

## 4. D1/D2/P05 — 三個獨立 Gate（2026-07-10～11，全部 FAIL/NO-GO）

同樣岔自 `5090`，各自是單次、封閉的可行性驗證：

- **d1-g0-persistence-existence**（07-10）：BLOCK verdict on map-build reliability（session1/session2 capture + GT exclusion mask）。
- **d1-g1-starvation-shadow**（07-11）：**FAIL**——shadow-evaluate BoW 8-14 候選（低於線上 ≥15 門檻）在飢餓與對照組都拿不到任何 PnP pose，沒有可回收的東西。
- **d2-g1-attribution-change**（07-11）：**FAIL**——幾何驗證的 inlier/reject 結果與跨 session 變化訊號無關（AUROC 0.518，等同亂猜）。
- **p05-g1-runtime-reloc-logging**（07-11）：**NO-GO**——oracle 式 map-maintenance（隔離已變化的點）相較 keep-all 沒有重定位餘裕，reloc 成功率打平、但 inlier/timing 更差。

## 5. NSAVP / TCAF — 跨模態相機-熱像儀對齊（2026-07-12～13，最新收斂）

`nsavp-cross-modal` 分支，HEAD `b76d90df`（2026-07-13）。Stage 0-4 完成細節見 memory `reference_nsavp_20260712.md`、`project_tcaf_first_closed_loop_20260712.md`：

- 修正了 frame-chain 一個關鍵 bug（`measured_extrinsics` 缺少 housing→optical 90° 旋轉，曾讓 GT/PnP 方向正交）。
- 發現 night RGB→RGB 對齊完全失效（NCC 0.047），但 day-RGB↔night-thermal 邊緣對齊訊號強 4 倍（0.208），尤其在側向/偏航方向。
- TCAF（curvature-λ + p_outlier 的最小可行版本）在受控閉環評估中打贏純 VO 與兩個經典各向同性 baseline，是這整個 XT-G/NSAVP 探索裡少見的**正結果**。
- **本次稽核新發現**：G4 階段（`tcaf/reports/G4_learned_feature_cost.md`，07-13）——嘗試把手工 Sobel-NCC cost 換成訓練式跨光譜特徵 encoder，結果**NO GAIN / STOP**：InfoNCE 表現接近或低於隨機，回收的錨點誤差（6.64m）反而比既有手工方法（6.20m）差，訊號太弱學不起來。**決策：系統地圖整合前先停下**，不再往這個方向加碼。

## 6. SPECTRA-Landmark-Lifecycle（2026-07-13，最新分支，先前無 memory 記錄）

`spectra-landmark-lifecycle` 分支，HEAD `ce9754e1`（2026-07-13），是本次稽核發現的**全新分支，之前的對話/memory 都沒有記錄**。依 `vivid/HANDOFF_AFTER_VIVID_C0.md`：

- 使用 ViViD 資料集，**C0 gate 最終 PASS**（完整 day1+night1，false-merge 0%，CI 區間 [0,0]）。
- Handoff 文件指示下一步是原生 ORB-SLAM3 RGB-D baseline，走 C1→C2→C3→FINAL_VERDICT 的 gate 序列——**這條線目前處於起步/交接狀態，尚未有後續 gate 結果**，是六條主題線裡唯一「還在往前走」而非已經 PASS/FAIL 收斂的。

## 7. 全景總結

| 主題線 | 分支數 | 狀態 | 一句話結論 |
|---|---|---|---|
| Evidence-Gated Gate (P2A) | 1（已推送） | 收斂於 P2A-2l | 離線信號+線上機制皆驗證安全，未跑到 SLAM 準確度評估 |
| Observation Lifecycle (C2) | 5 | 收斂 FAIL | 4-class 路由機制正確但零 ATE 效益，S4x 隔離實驗未核准 |
| 跨光譜地圖重定位 (XT-G) | 6 | 收斂於方法凍結 | 瓶頸在跨模態檢索/驗證，PDA 是唯一還在走的假說 |
| D1/D2/P05 三個獨立 Gate | 4 | 全部 FAIL/NO-GO/BLOCK | 三個相關可行性方向均無回收餘裕或訊號 |
| NSAVP/TCAF | 1 | 部分正結果，學習式擴充已停 | TCAF 最小版本正結果，G4 學習式特徵擴充 STOP |
| SPECTRA-Landmark-Lifecycle | 1 | 剛起步（C0 PASS） | 唯一仍在推進中的主題線 |

**最值得後續行動的兩個開放項目：**
1. `spectra-landmark-lifecycle` 是唯一活躍前進的分支，下一步是原生 RGB-D baseline（C1），值得先確認是否要繼續投入。
2. 除 `p2-a-evidence-gated-semantic-slam-spec` 外所有分支都還沒推送到 origin——如果要保留這些實驗歷史（尤其是剛發現、無 memory 記錄的 spectra 分支），建議近期做一次批次 push。

---
*資料來源：`5090` repo branch 稽核（`git for-each-ref`/`git log`/push 狀態核對）+ 既有 memory 系列（C2/P2A/XT-G/NSAVP/TCAF）交叉比對；本文件未執行任何新實驗，純盤點。*
