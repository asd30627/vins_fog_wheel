# Proposal — 以 FOG-wheel 運動參考估計逐特徵可靠度(動態場景)

## 大白話摘要(給非技術讀者)
**問題**:相機定位系統(VIO)假設看到的景物是靜止的。馬路上有車在動、有人在走時,系統把這些「會動的點」當成靜止地標來算自己的位置,於是算錯、飄移。

**為何值得做**:自駕車、送貨機器人都在有動態物體的真實街道上跑。現有方法多半靠「看起來像車/人就不要用」(語意分割)或「猜哪些點不一致」(統計),前者誤殺停著的車、後者在動態多時不穩。

**怎麼解**:車上本來就有兩個「不靠相機」的運動感測器——光纖陀螺(FOG,量轉向)與輪速計(量前進)。它們合起來能獨立算出「車子這一小段真正怎麼動」。拿這個獨立答案去檢查每一個影像特徵點:若某個點的移動和「車子的剛體運動」對不上,它就很可能在動,該降低信任。

**創新**:不發明新的深度學習網路,而是用「獨立、非視覺的運動參考」做逐特徵、規則式、有時間記憶的可靠度評估,並把它接回現有 VIO 的最佳化。深度學習只當一個可抽換的輔助元件(事前看外觀預判),不是主張。

**貢獻**:(1) 一個幾何系統框架,用 FOG-wheel 運動一致性判定逐特徵可靠度;(2) 時間記憶機制(易疑難信)避免單幀誤判;(3) 在動態場景對 VINS-Fusion 的定位改善,並以消融顯示 learned head 的邊際價值。

## Why
動態物體違反 VIO 的剛體靜態世界假設,是街道場景漂移的主因。FOG-wheel 提供一個與相機獨立的運動參考:特徵點的重投影殘差在「該特徵屬於靜止世界」假設下,可用 FOG-wheel 預測的相對運動檢驗(已 code-freeze 的 wheel SE(2) 因子提供平移,FOG 提供 yaw)。動態特徵的殘差會系統性偏大,可被偵測並降權。此路線承接已完成的工程資產(wheel SE(2) 因子、integrity 標籤管線),且在動態場景幾何一致性最乾淨。

## What Changes
- 新增能力 `feature-reliability`:逐特徵可靠度純量的計算、時間記憶、防退化、接入 VINS 的位置。
- 新增能力 `motion-reference-consistency`:FOG(yaw)+ wheel SE(2)(平移)組成的獨立運動參考,與每特徵重投影的一致性度量(Mahalanobis)。
- 評估協定:動態場景下對 VINS-Fusion baseline 的定位改善 + 規則式 vs +learned head 消融。
- 動態特徵標籤:修復 CARLA instance-id≠actor-id(只設計,執行待核准)。

## Non-goals(本變更不含)
- 外觀退化(低紋理/眩光/霧):列第二章/future(需學習式 metric covariance branch)。
- 完整 SO(3) FOG 旋轉因子:FOG 只約束 yaw(D16/X7)。
- 像素/深度 metric covariance(MAC-VO 正面比):future extension(D17)。
- 新深度學習架構主張(X4);learned head 為可抽換元件(D15/D17)。
- 反向傳播穿過 Ceres / 可微分 VIO(已於先前 session 否決)。

## 與相關研究的概念差異
| 方法 | 核心 | 與本提案差異 |
|---|---|---|
| DynaVINS | 視覺殘差加權 + 回歸式剔除動態 | 本提案用**非視覺獨立運動參考**判定,不靠視覺自洽(動態多時更穩) |
| PL-VIWO2 | 點線 + 輪速里程 VIO | 本提案的輪速進**逐特徵可靠度**,非僅作里程因子 |
| MAC-VO | learned metric covariance(像素+深度) | 本提案主張幾何規則式可靠度;metric covariance 列 future,正面比較留第二章 |
| 一般 VIWO | wheel 作運動約束 | 本提案 wheel + FOG 作**可靠度的獨立檢驗源**,非僅狀態約束 |

## Impact
- Specs:新增 `feature-reliability`、`motion-reference-consistency`。
- 程式:接入點為 VINS sliding-window 的逐特徵權重(沿用既有 visual_alpha / projection sqrt_info hook);估計器主體不重寫。
- 依賴:多個 task gated on Phase B `b1_se2_vs_b0.csv`(wheel SE(2) 贏多少決定可靠度該多依賴幾何)。

## Unresolved(需使用者回來定,勿自行發明)
- 可靠度計算法三案擇一:硬門檻 / 連續權重 / 因子圖潛在可靠度狀態(D7)。設計比較見 `designs/reliability-computation.md`。
- 時間記憶(D6 快降慢升)參數與恢復條件:`designs/temporal-memory.md`。
- 防可靠度退化至零機制:`designs/anti-degeneracy.md`。
- NHC 是否進系統:gated on B1-SE2 結果(`NHC_DESIGN.md`)。
- 動態評估協定 + CARLA instance-id 修復細節:`designs/dynamic-eval-and-labels.md`。
