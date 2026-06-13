# 設計短文 — 動態場景評估協定 + 動態特徵標籤(T6, T7)

## A. 評估協定(T6)
**推薦預設:VINS-Fusion 為必要 baseline(D19),SE(3)-only 對齊(無 scale),動態場景分層,規則式 vs +learned head 消融。**

| 項 | 設定 | 依據 |
|---|---|---|
| baseline | VINS-Fusion(必要);DynaVINS(選用,視時程) | D19 |
| 對齊 | SE(3) rigid,**禁 Sim(3) scale**(stereo 尺度可觀測) | eval_kaist.py 已實作 |
| 指標 | ATE {median,p95,p99}、RPE {1s,10s}、body lon/lat p95 | 沿 v3.1 凍結 |
| 分層 | 動態密度(靜/中/高)分層報 ratio | 動態場景主張需分層 |
| 消融 | B0 / B1-SE2 / B1-SE2+reliability(規則式) / +learned head | D15 主貢獻幾何、learned 為加掛項 |
| 判讀 | 8/8 完跑、p95-ATE ratio 中位<0.90=明確改善、≥6/8 不惡化>10% | v3.1 凍結門檻 |
| dev seq | urban28 為 development,主統計另報其餘 7 條 | 防 overfit |
- **gated**:動態場景的 wheel-only 改善幅度待 Phase B `b1_se2_vs_b0.csv` 補上;決定 reliability 該多依賴幾何 vs learned head。

## B. 動態特徵標籤 — CARLA instance-id 修復計畫(T7,只設計不執行)
**問題(已證)**:CARLA 0.9.16 instance-seg 的 (G,B) 編碼 ≠ CARLA actor.id(zero intersection;seg id ~30k 內部計數,actor id <256)。故無法直接 seg-id → gt per_instance[actor_id].speed join。

**推薦修復:actor 投影關聯(不靠 seg-id 對應)**
1. 每幀對每個 GT vehicle/pedestrian actor,用 ego_pose + camera 外參/內參把 actor 3D bounding box 投影到左影像 → 2D 遮罩。
2. 特徵點落入某 actor 投影遮罩 → 指派該 actor 的 GT world speed;落在背景 → speed=0(靜止世界)。
3. staticness label = (obj_speed < static_speed_thresh_ms=0.15),class-agnostic(停車=靜止,正確)。
4. 驗證:抽 10 個移動車像素 + 10 個停車/背景像素,人工核對指派的 speed(取代舊「全場最大車速」誤標停車為動態的近似)。

**紅線**:不以 GT depth 當網路輸入(D18);只用於標籤生成,不洩漏進 learned head 輸入。
- **執行待核准**:本 task 只到計畫;CARLA 重採集/重標由使用者核准後另跑(禁在 Phase B 期間動 CARLA/build)。
