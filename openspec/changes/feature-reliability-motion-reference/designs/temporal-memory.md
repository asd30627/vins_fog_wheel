# 設計短文 — 時間記憶(T3,D6 快降慢升)

**推薦預設:非對稱指數遲滯,drop_kf=2 / restore_kf=8,τ_drop=0.30 / τ_restore=0.80,恢復需連續一致。** 沿用 integrity 既有值為起點。

## 機制
每特徵維護平滑可靠度 r_t。每 keyframe 由瞬時可靠度 r_inst(來自 d²,見 reliability-computation)更新:
- **降權(快)**:若 r_inst < τ_drop 連續 drop_kf 幀 → r_t 快速下降(時間常數短)。
- **恢復(慢)**:若 r_inst > τ_restore 連續 restore_kf 幀 → r_t 緩慢回升(時間常數長,w_recover/w_drop≈4)。
- 介於 τ_drop 與 τ_restore 之間 → 維持(遲滯帶,防抖動)。

## 參數(起點,可調)
| 參數 | 值 | 依據 |
|---|---|---|
| τ_drop / τ_restore | 0.30 / 0.80 | integrity reliability_memory 既有;drop<restore = 易疑難信 |
| drop_kf / restore_kf | 2 / 8 | 快降(1–2 幀)慢升(5–10 幀),proposal §4.3 |
| w_recover/w_drop | 4.0 | 恢復剛性 > 降權,抗過早回信 |
| sustained_kf(改信任最小證據) | 5 | 非單幀 outlier(§5.2) |

## 恢復條件
特徵須(1)持續被追蹤(track_age 足夠)、(2)連續 restore_kf 幀 r_inst>τ_restore,才回升。一旦中斷一致 → 計數歸零。重新出現的 track 視為新特徵(不繼承舊 r_t)。

## 與防退化的關係
時間記憶不得使全幀可靠度集體歸零;下限保護見 `anti-degeneracy.md`(T4)。
