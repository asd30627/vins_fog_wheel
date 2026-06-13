# Explore Session Notes
**Change**: 無(研究方向收斂,承 2026-06-12-fwvio-professor-report)
**Date**: 2026-06-13

## Confirmed Decisions

### D14. 第一篇範圍鎖「動態物體」,外觀退化列第二章
第一篇主打動態物體場景。FOG-wheel 幾何一致性在動態場景乾淨成立(特徵違反剛體世界假設→運動殘差大→可偵測),且規則式即可成立,貼近 wheel SE(2) 已 code-freeze 的工程進度。低紋理/眩光/霧等外觀退化列為第二章/future,因為該場景幾何一致性最使不上力、需要學習式 covariance branch。
Draft Link: working-draft#問題定義

### D15. 主貢獻定位為幾何,深度學習為元件
主貢獻 = 用 FOG-wheel 獨立運動參考估計逐特徵可靠度(幾何、規則式、具時間記憶)。深度學習以「可抽換元件」身分進入,非「新深度學習架構」的主張。論文 claim 是幾何系統框架;learned head 是其中一個模組,paper 1 可當 ablation 加掛項(規則式可靠度 vs +learned head)。
Draft Link: working-draft#預期研究貢獻

### D16. FOG 只約束 yaw
FOG 以 yaw 偏航角約束進入系統,不做完整 SO(3)。依據:P1a 已證換 gyro 救不了位置;v3.2 已測 wheel yaw 漂 2–13°/min 不可信(Ackermann 側滑)→ 旋轉交 FOG、平移交 wheel SE(2),分工明確。
Draft Link: working-draft#感測器職責

### D17. 學習元件輸出逐特徵可靠度純量
learned head 輸出逐特徵可靠度純量(非 metric covariance)。依據:重用現有 VI-DCNet detector(AUPRC/calibration/lead-time 投入不浪費);訓練最輕;看影像外觀「事前」預判退化,與幾何殘差「事後」檢查互補。像素/深度 metric covariance 列 future extension(真要與 MAC-VO 正面比時再上)。
Draft Link: working-draft#深度學習元件

### D18. 學習元件標籤採 CARLA 建標籤 + KAIST 驗遷移
CARLA 提供獨立標籤、KAIST 驗 sim-to-real 遷移,重用既有 integrity 標籤管線。前提:(1) 先修 instance-id≠actor-id;(2) 不以 GT depth 當輸入。
Draft Link: working-draft#深度學習元件

### D19. Baseline
VINS-Fusion 為必要 baseline;DynaVINS 視時程為選用。

## Rejected Options (with Reasons)

### X4. 把深度學習架構當主創新
最擁擠(DynaVINS / MAC-VO 系列)、最難做出新意、時間最不夠;且 FOG-as-global-detector 框架已被推翻、CARLA 標籤未修。強系統/幾何論文在 ICRA/IROS/RA-L 不需 DL 新穎性即可成立。

### X5. 把動態+外觀焊成單一 claim
兩場景需不同機制(動態=幾何一致性;外觀=學習式 covariance)。焊成一個 claim = 最重、最沒收斂、最可能畢不了業的版本。改以分階段化解。

### X6. 用 FOG-wheel 殘差做學習元件的自監督標籤
與幾何核心循環論證:learned head 只會學成模仿幾何訊號,不增加資訊。

### X7. FOG 完整 SO(3) 旋轉因子
roll/pitch 可觀測性需另處理,且與 wheel SE(2) 平面約束資訊重疊;yaw-only 最乾淨。

## Future Change Drafts
- 外觀退化第二章:learned metric covariance(像素+深度)+ MAC-VO 正面比較。
- 規則式可靠度提升為因子圖中的選擇性潛在可靠度狀態(D7)。

## Unresolved Issues
- 規則式可靠度的具體計算:硬門檻 / 連續權重 / 因子圖潛在可靠度狀態(D7),擇一。
- 時間記憶機制(D6 快降慢升)的參數與恢復條件。
- 防可靠度退化至零的機制與驗證方法。
- NHC 是否進系統:gated on B1-SE2 paired 結果(現正跑 Phase B)。
- 視覺退化場景的評估標準與消融設計(動態場景的 dynamic-feature 標籤來源,需 CARLA instance-id 修復)。

## Scope Confirmation for Current Change
- 範圍內:第一篇研究敘事、主貢獻定位、感測器分工、學習元件身分與形狀(方向級)、baseline、分階段邊界。
- 範圍外:規則式可靠度的最終演算法細節、學習網路最終架構、尚未驗證的實驗改善宣稱。
