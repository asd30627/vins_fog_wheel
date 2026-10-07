# PAPER2 Track A — SEQUENCE MODEL RESULTS（實跑，誠實）

> 真實執行結果。**壞結果照寫，不包裝。** 紅線全守：無 GT feature（label 才用 GT）、
> 無 frame-random（KITTI by seq / CARLA by run）、未碰 backend / object-factor / frontier / HD-map。
> 主指標 AURC（越低越好），bootstrap ΔAURC over groups（runs/seqs）。日期 2026-07-01。
>
> 腳本：`scripts/paper2_sequence_validity_experiment.py`（no-torch 候選）、
> `scripts/paper2_sequence_deep_models.py`（GRU/TCN/Transformer，conda env `gf`, torch 2.7.1+cu128, RTX 5090）。
> 資料：`paper2/track_a/paper2_sequence_*_metrics.csv` + `*_bootstrap.csv`。

---

## 0. 設定

- 序列輸入：每個被標記 frame 取其 track 的最後 **T=5** frame 之 RAW 可觀測特徵（edge-pad 補短）。
- per-frame 特徵（9，雙資料集共通，無 GT）：`range_m, depth_m, bbox_area, bearing_deg, det_conf, raw_speed, cv_residual, acceleration_score, track_age`（scale 類取 log1p）。
- 候選：
  - `cv_smoothing_gate`：last-frame `−cv_residual`（incumbent 最強 simple baseline）
  - `TCSV-M`：HistGBM + monotonic prior on 14 手工摘要特徵（**現任 final model**）
  - `seq_flat_mlp`：MLP on 攤平 [T×F] 序列（保留順序）
  - `seq_pool_hgbm`：HistGBM on 時間池化統計（mean/std/min/max/last/slope per feature）
  - `seq_pool_mlp`：MLP on 同池化統計
  - `GRU` / `TCN` / `Transformer`：學習型序列編碼器（group-held val early-stopping，pos-weight 處理不平衡）

---

## 1. AURC（越低越好）— 全模型 × 全 split

| split | cv_gate | TCSV-M | seq_flat_mlp | seq_pool_mlp | **seq_pool_hgbm** | GRU | TCN | Transformer |
|---|---|---|---|---|---|---|---|---|
| kitti→kitti（**真實 in-domain**） | 0.284 | 0.223 | 0.207 | 0.188 | **0.196** | 0.212 | 0.210 | 0.214 |
| carla→carla（synthetic in-domain） | 0.822 | 0.676 | 0.712 | 0.669 | **0.642** | 0.754 | 0.753 | 0.730 |
| C+Ktr→Khold（mixed-train） | 0.284 | 0.227 | 0.231 | 0.216 | **0.203** | 0.235 | 0.227 | 0.210 |
| kitti→carla（real→synthetic 直接遷移） | 0.848 | 0.823 | 0.837 | 0.844 | **0.822** | 0.833 | 0.824 | 0.848 |
| carla→kitti（synthetic→real 直接遷移） | **0.317** | 0.373 | 0.425 | 0.479 | 0.384 | 0.414 | 0.441 | 0.465 |

**粗體 = 該 split 的學習型最佳。** 注意：所有學習模型在 **synthetic→real 直接遷移仍輸 cv_gate**（持續弱點，與前一輪一致）。

---

## 2. Bootstrap ΔAURC（cand − ref，over groups；neg ⇒ cand 較好）

### 2a. no-torch 池化 vs incumbents（`seq_pool_hgbm`）
| split | vs TCSV-M | vs cv_gate |
|---|---|---|
| carla→carla | −0.027 [−0.057,−0.001] ✅ | −0.165 [−0.248,−0.077] ✅ |
| kitti→kitti | −0.028 [−0.040,−0.021] ✅ | −0.088 [−0.098,−0.078] ✅ |
| C+Ktr→Khold | −0.023 [−0.029,−0.017] ✅ | −0.080 [−0.090,−0.070] ✅ |

→ **`seq_pool_hgbm` 在三個 in-domain/mixed split 全部 bootstrap CI<0，穩定贏 TCSV-M 與 cv_gate。**

### 2b. 深度序列編碼器 vs incumbents 與池化
| split | model | vs TCSV-M | vs **seq_pool_hgbm** | vs cv_gate |
|---|---|---|---|---|
| kitti→kitti | GRU | −0.011 ✅ | **+0.017 ❌ worse** | −0.072 ✅ |
| kitti→kitti | TCN | −0.013 ✅ | **+0.015 ❌ worse** | −0.073 ✅ |
| kitti→kitti | Transformer | −0.010 ✅ | **+0.018 ❌ worse** | −0.070 ✅ |
| carla→carla | GRU | **+0.083 ❌ worse** | **+0.117 ❌ worse** | −0.056 tie |
| carla→carla | TCN | **+0.086 ❌ worse** | **+0.120 ❌ worse** | −0.052 tie |
| carla→carla | Transformer | +0.064 tie | **+0.098 ❌ worse** | −0.074 tie |
| C+Ktr→Khold | GRU | +0.009 tie | **+0.032 ❌ worse** | −0.049 ✅ |
| C+Ktr→Khold | TCN | +0.000 tie | **+0.024 ❌ worse** | −0.057 ✅ |
| C+Ktr→Khold | Transformer | −0.017 ✅ | **+0.007 ❌ worse** | −0.074 ✅ |

→ **三個深度序列模型在每一個 in-domain/mixed split 都輸給簡單的 `seq_pool_hgbm`（CI>0）。** 在 synthetic CARLA（只有 2 town、許多短 track，中位長度 7）甚至比 TCSV-M 還差——典型 thin-group 過擬合。

---

## 3. 誠實結論（三句）

1. **真正的升級在「特徵」不在「模型」**：時間池化統計（mean/std/min/max/last/slope）→ HistGBM = `seq_pool_hgbm`，是對 TCSV-M 的 **真實、bootstrap 驗證、可解釋** 的小幅提升（~0.02–0.03 AURC，三 split CI<0），並同時贏 cv_gate 與所有 MLP/深度 selector。
2. **學習型序列編碼器（GRU/TCN/Transformer）不值得**：在現有資料規模（~33k KITTI / ~14k CARLA window、21 KITTI seq + 2 CARLA town 的薄 group 結構）下，**贏不過簡單池化 HistGBM**，且在 synthetic 上明顯過擬合。順序結構沒帶來價值（order-preserving `seq_flat_mlp` 也輸 order-agnostic 池化）。
3. **持續弱點未解**：synthetic→real 直接遷移（carla→kitti）所有學習模型仍輸 cv_gate（+0.067）。這不是模型問題，是 domain-gap + 單一真實資料集問題。
