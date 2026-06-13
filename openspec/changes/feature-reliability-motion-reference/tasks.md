# Tasks — feature-reliability-motion-reference

每個 task = 一個可被 review 的設計決策。狀態:☐ 待核准(本 session 只到設計;C++ 實作待使用者核准本檔後,以 commit-ladder + gates 進行)。

## T1. 運動參考一致性度量(motion-reference-consistency)
- **決策**:定義 FOG(yaw)+ wheel SE(2)(平移)組成的每特徵重投影一致性統計(Mahalanobis d²),含協方差預算來源(wheel SE(2) cov + FOG yaw cov + 像素 cov)。
- **依賴**:wheel SE(2) 因子(已 code-freeze);FOG yaw 待 `FOG_FACTOR_DESIGN.md` 實作(另案)。
- **產物**:`specs/motion-reference-consistency/spec.md` + `designs/reliability-computation.md` §一致性度量。
- **驗收**:靜止特徵 d²≈χ²(2) 量級、動態特徵 d² 明顯偏高(沿用 anchor sanity 方法,真實 KAIST 驗證)。

## T2. 逐特徵可靠度計算法(三案擇一)— **需使用者決策**
- **決策**:硬門檻 / 連續權重 / 因子圖潛在可靠度狀態(D7),擇一為 paper-1 主法。
- **依賴**:**gated on Phase B `b1_se2_vs_b0.csv`**(wheel SE(2) 贏多少 → 幾何訊號可信度 → 該多依賴幾何 vs learned head)。
- **產物**:`designs/reliability-computation.md`(三案 + 推薦預設)。
- **驗收**:使用者點選一案;選定後可寫成 spec requirement。

## T3. 時間記憶機制(D6 快降慢升)
- **決策**:可靠度的時間濾波參數(drop/restore 門檻、drop_kf/restore_kf、恢復條件)。
- **依賴**:T2 選定計算法後定參數;沿用 `cov-clean`/integrity 既有 τ_drop=0.30 / τ_restore=0.80 為起點。
- **產物**:`designs/temporal-memory.md`。
- **驗收**:單幀誤判不致命(需連續 k 幀證據才改信任);參數有依據不隨手填。

## T4. 防可靠度退化至零
- **決策**:避免所有特徵被降權致退化的機制(每幀最少可信特徵數下限 + 對稱性檢查)+ 驗證法。
- **依賴**:無(獨立工程安全閥)。
- **產物**:`designs/anti-degeneracy.md`。
- **驗收**:構造退化情境(全動態視野)下系統不崩、有下限保護。

## T5. 接入 VINS 的位置
- **決策**:可靠度純量如何進最佳化——重用既有 `visual_alpha` / `ProjectionTwoFrameXFactor::sqrt_info=√alpha·FOCAL/1.5` hook(逐特徵 alpha),不重寫估計器。
- **依賴**:T2(可靠度→alpha 映射)。
- **產物**:`specs/feature-reliability/spec.md` §接入點;引用既有 hook。
- **驗收**:flags-off 位元不變(沿 wheel 的 code-freeze 紀律);逐特徵 alpha 路徑可關閉。

## T6. 評估協定(動態場景)
- **決策**:baseline(VINS-Fusion 必要、DynaVINS 選用 D19);指標(ATE SE(3)、RPE、動態場景分層);消融(規則式 vs +learned head)。
- **依賴**:T7 標籤;Phase B 數字補上動態場景的 wheel-only 改善。
- **產物**:`designs/dynamic-eval-and-labels.md` §評估協定。
- **驗收**:預註冊判讀門檻(沿 v3.1 凍結);urban28 為 development、主統計另報。

## T7. 動態特徵標籤(CARLA instance-id 修復)
- **決策**:修復 CARLA 0.9.16 instance-seg id≠actor-id(已證 zero intersection)——改用 actor 投影關聯;不以 GT depth 當輸入(D18)。
- **依賴**:無(純資料管線,只設計不執行)。
- **產物**:`designs/dynamic-eval-and-labels.md` §標籤修復計畫。
- **驗收**:設計含 id 對應驗證樣本表計畫;執行待核准。

## T8. learned head 身分與形狀(D15/D17)
- **決策**:learned head 輸出逐特徵可靠度純量(非 metric covariance);重用 VI-DCNet detector;以可抽換元件 + 消融加掛項定位。
- **依賴**:T2、T6。
- **產物**:`specs/feature-reliability/spec.md` §learned head 介面(輸入=影像外觀,輸出=純量,與幾何殘差互補)。
- **驗收**:介面定義使規則式與 +learned 可獨立開關做消融。
