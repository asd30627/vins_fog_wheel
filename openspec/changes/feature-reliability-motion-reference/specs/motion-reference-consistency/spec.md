# Spec — motion-reference-consistency

## Purpose
提供與相機獨立的車體運動參考(FOG yaw + wheel SE(2) 平移),並對每個影像特徵計算「該特徵屬於靜止世界」假設下的重投影一致性統計,作為可靠度判定的事後幾何證據。

## ADDED Requirements

### Requirement: 獨立運動參考組裝
系統必須由非視覺感測器組裝相鄰 keyframe 間的相對運動參考:旋轉(yaw)來自 FOG、平移來自 wheel SE(2) preintegration,兩者不得使用任何視覺特徵。

#### Scenario: wheel 提供平移、FOG 提供 yaw
- **WHEN** 形成 keyframe j(時間 Headers[j])
- **THEN** 系統以 wheel SE(2) preintegration[j] 取得 (Δx, Δy, Δyaw_wheel),並以 FOG yaw 增量取代 Δyaw_wheel(wheel yaw 已測 2–13°/min 不可信)
- **AND** 該運動參考與相機特徵完全獨立

#### Scenario: interval 無效時不產生參考
- **WHEN** wheel preintegration[j].valid == false(樣本 0 或 coverage-wait 超時)
- **THEN** 該 interval 不提供運動參考,依賴此參考的可靠度更新標記為 ignore,不得用半段資料

### Requirement: 逐特徵一致性統計
系統必須對每個被追蹤特徵計算 Mahalanobis 一致性 d²,協方差預算須包含 wheel SE(2)、FOG yaw、像素三來源,不得只用單一固定像素門檻。

#### Scenario: 靜止特徵低 d²
- **WHEN** 特徵屬於靜止世界且外參/同步正確
- **THEN** d² 集中在 χ²(2 dof) 量級(與 static_maha_max 同量級)

#### Scenario: 動態特徵高 d²
- **WHEN** 特徵位於相對車體運動的移動物體上
- **THEN** d² 系統性偏高,與靜止特徵分布明顯可分(真實資料上以 KAIST 驗證,合成正控制驗證可分性)

#### Scenario: 協方差來源缺失的退化保護
- **WHEN** 像素協方差 Σ_uv 尚未由 learned head 提供
- **THEN** 使用文件記錄的標稱值(非過緊 1px²),且 d² 的絕對量級依賴此標稱值一事須在報告中標明
