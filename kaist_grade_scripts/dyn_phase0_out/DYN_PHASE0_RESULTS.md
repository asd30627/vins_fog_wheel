# 方向一 Phase 0 可行性驗證 — 動態物體 vs KAIST VIO 視覺退化

> 日期 2026-06-29。目標:在投入語意分割 pipeline 前,先確認前提
> 「KAIST 的視覺退化是不是真的跟動態物體有關?」誠實報告,結論決定要不要進 Phase 1。

## TL;DR(判斷)
**動態物體不是 urban26/urban28 視覺退化的有意義來源,且若有關係是「反向」的(動態越多、視覺越健康)。**
依現有證據,方向一(rule-based 語意剔除動態特徵)**不建議直接做**;唯一可能翻案的窄縫見 §6。

---

## 1. 方法(誠實標註偏離原指令處)
- 偵測:pretrained **YOLOv8m (COCO)**,**不訓練**;movable 類別 = {person, bicycle, car, motorcycle, bus, truck}。imgsz=1280, conf=0.25, GPU RTX 5090。
- 影像:KAIST `stereo_left` 1280×560 bayer,`COLOR_BayerRG2BGR` 還原(已用天空 B>R 驗證為正確 pattern)。檔名 ns = capture ts,與 keyframe ts **完美對齊**(末張 1544581289.8215 ≈ CSV 末列;matched 117/2467,miss=0)。
- **⚠ 與原指令的偏離**:原指令 step 3-4 要「每個 VINS 特徵點落在 bbox 內外」。但現存
  `feat_snapshots/*__lastgrade.csv` 是 **per-keyframe 聚合**(count/coverage/entropy/殘差/est_p),**沒有 per-feature 像素座標**。要逐點比對需改 VINS dump 每點座標 + 重 replay(昂貴)。
  → 改做 **keyframe-level**:每張 keyframe 的「動態物體像素佔比 dyn_area_frac」對上 VINS 自己的退化 proxy。
  這是 per-feature 假設的**必要條件**:若連 image-level「動態多→VIO 差」都不成立,per-feature 故事幾乎不可能成立。**零 VINS 變更、零重跑。**
- 退化 proxy(全部 runtime-observable,免 GT 對齊):`vg_flow_res_mean`(reproj 殘差代理)、`outlier_ratio_last`(VINS 自己的 RANSAC 剔除率)、`inlier_count_last`、`tracked_feature_count_mgr`、`coverage_8x8`。
- 規模:urban26-dongtan n=1942(stride3)、urban28-pankyo n=2467(stride8)。

## 2. 動態內容確實存在(前提的前半成立)
| seq | 有物體的 keyframe 比例 | dyn_area_frac median | p90 | max |
|---|---|---|---|---|
| urban26-dongtan | 92.1% | 3.2% | 20.3% | 53.7% |
| urban28-pankyo | 97.0% | 3.5% | 21.7% | 55.9% |

→ 兩序列都是動態密集場景(>90% keyframe 有車/人),所以「沒東西可偵測」不是問題。疊圖(`overlays/`)確認 YOLO 在路口把卡車/巴士/多台車精準框出,顏色與框都正確、可信。

## 3. 核心結果:動態佔比 vs 視覺退化是「反向」的
**Spearman(dyn_area_frac, proxy):**
| seq | vs vg_res(殘差) | vs outlier | vs inlier | vs feat_count | vs coverage8 |
|---|---|---|---|---|---|
| urban26 | **−0.36** | −0.14 | +0.29 | +0.29 | −0.14 |
| urban28 | **−0.20** | −0.13 | +0.20 | +0.19 | +0.17 |

殘差負相關 = 動態物體越多、reproj 殘差越**低**(視覺越好)。inlier/特徵數正相關 = 動態多的場景特徵更多。

**四分位分箱(urban26,單調最清楚):**
| 分箱 | dyn_frac | vg_res 殘差 | outlier | inlier |
|---|---|---|---|---|
| Q1 最少動態 | 0.2% | 0.084 | 0.0053 | 112 |
| Q2 | 1.5% | 0.086 | 0.0057 | 119 |
| Q3 | 6.6% | 0.066 | 0.0059 | 125 |
| **Q4 最多動態** | 20.5% | **0.032** | **0.0021** | **128** |

動態最多的那一檔殘差最低(降 ~2.6×)、outlier 最低、inlier 最高。urban28 同向(vg_res 0.074→0.042)。

## 4. 連最嚴格的「救援假設」也失敗
假設「只有大型近距車輛(擋住前方紋理的移動卡車/巴士)才傷 VIO」→ 用 `dyn_max_frac`(最大單一物體佔比)前 10% frame:
| seq | big-obj frame 殘差 | 其餘 frame 殘差 | big-obj outlier | 其餘 outlier |
|---|---|---|---|---|
| urban26 | 0.047 | 0.069 | 0.0034 | 0.0049 |
| urban28 | 0.033 | 0.066 | 0.0036 | 0.0055 |

大型近距車輛 frame 殘差**更低**、outlier**更低**。原因見疊圖:這些 frame 多在路口/車陣,**同時也是建築/招牌/斑馬線/路緣最密**的高紋理場景,VINS 的 RANSAC 又把移動點當 outlier 剔掉了。

## 5. 為什麼是這個結果(機制)
1. **混淆變數 = 場景紋理**:有車有人的地方(路口、市區)本身建築/標誌密 → 特徵又多又好。動態物體帶來的少量壞點被淹沒。
2. **VINS 已有 outlier 機制**:移動點本來就會被 RANSAC/反投影殘差剔除(outlier_ratio 在高動態時反而更低)。
3. **與三個月前發現一致**:低信任視覺特徵「不是動態物體,是近距/高視差幾何弱點」。語意換成真 YOLO 後**同一結論**。
4. **與 grade-hard 結論一致**:KAIST 崩潰是 xsens **acc-bias / scale 不可觀測**(長直線 highway),與相機看到什麼物體正交。動態物體救不了那種崩潰,也不是它造成的。

## 6. 唯一可能翻案的窄縫(誠實標註)
本分析把 **movable 類別**全算動態,包含**路邊停放車輛(其實是靜態、且是好特徵)**。真正會傷 VIO 的是「**真的在動**」的點,不是「可能會動的類別」。停放車的紅利可能**遮蔽**了少數真移動車的害處。
- 但要分離「真移動 vs 停放」需 ego-motion 補償後的 per-object 光流殘差 / 移動分類 → 這正是昂貴的 per-feature/per-object 路線。
- 量級判斷:即使翻案,upside 被 §3 的強反向關係**上界**住了——在 surviving 序列上殘差/outlier 已經很低,動態剔除能搶救的 ATE 空間很小。

## 7. 建議(待你裁示,不自行進 Phase 1)
1. **不建議**直接做方向一 rule-based 動態剔除:在 urban26/28 上前提不成立。
2. 若仍要救 §6 窄縫,**最小代價驗證**應是:對「真移動物體」(光流/tracking 篩出,非 movable 類別)做同樣相關分析;**仍只需 keyframe-level、不需改 VINS**。這是進 Phase 1 前的最後一道 gate。
3. per-feature 逐點剔除(需改 VINS dump + replay)在 §6 窄縫未驗證前**不投入**。

## 附:檔案
- 腳本:`kaist_grade_scripts/dyn_phase0.py`(env: conda `gf`,已裝 ultralytics 8.4.82)
- 資料:`urban26_full.tsv` / `urban28_full.tsv`(+ `.summary.json`),per-keyframe dyn 指標 + proxy
- 疊圖:`overlays/`(urban26 路口高動態 + urban28 各時段)
