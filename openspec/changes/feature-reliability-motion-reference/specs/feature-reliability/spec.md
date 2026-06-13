# Spec — feature-reliability

## Purpose
將每個特徵的運動一致性證據,轉成具時間記憶、防退化的逐特徵可靠度純量,並接回 VINS 最佳化的逐特徵權重,降低動態物體對定位的污染。

## ADDED Requirements

### Requirement: 逐特徵可靠度純量
系統必須為每個被追蹤特徵維護一個 [0,1] 可靠度純量,由 motion-reference-consistency 的 d² 證據驅動(計算法待 T2 決策),可選由 learned head(外觀事前預判)補充。

#### Scenario: 幾何證據降低可靠度
- **WHEN** 特徵連續多幀 d² 高於動態門檻
- **THEN** 其可靠度純量下降,對應的視覺殘差權重下降

#### Scenario: learned head 為可抽換元件
- **WHEN** learned head 關閉
- **THEN** 系統以純規則式可靠度運作(消融基線);開啟時 learned 純量與幾何證據互補融合,不得使 learned 成為唯一來源

### Requirement: 時間記憶(易疑難信)
可靠度更新必須非對稱:快速降權、緩慢恢復,且需連續證據(非單幀)才改變信任,避免單幀誤判致命。

#### Scenario: 單幀高殘差不立即剔除
- **WHEN** 特徵單一 keyframe d² 偏高但前後正常
- **THEN** 可靠度小幅下降,不直接歸零(需持續 drop_kf 幀證據)

#### Scenario: 恢復比降權慢
- **WHEN** 一個曾被降權的特徵恢復一致
- **THEN** 其可靠度回升所需幀數(restore_kf)明顯大於降權所需(drop_kf)

### Requirement: 防可靠度退化至零
系統必須保證每幀參與最佳化的可信特徵數不低於工程下限,避免全特徵被降權導致最佳化退化。

#### Scenario: 全動態視野的下限保護
- **WHEN** 一幀內幾乎所有特徵 d² 皆高(視野被動態物體佔滿)
- **THEN** 系統保留 reliability 最高的至少 N 個特徵(min_features_per_frame),不使有效特徵數歸零

### Requirement: 接入 VINS 的位置與可關閉性
可靠度純量必須透過既有的逐特徵視覺權重 hook 接入(visual_alpha → ProjectionTwoFrameXFactor sqrt_info),不得重寫估計器主體;且整條路徑須能以開關關閉以保 flags-off 位元不變。

#### Scenario: flags-off 位元不變
- **WHEN** feature-reliability 開關關閉
- **THEN** VINS 輸出與未接入此能力的 code-freeze 基線位元相同(沿 wheel SE(2) 的 code-freeze 紀律)
