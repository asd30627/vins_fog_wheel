# PAPER2 DAYTIME A2 SUMMARY — does VINS-quality-conditioned NOUE hold? (2026-06-30)

> 唯一目的：裁決核心新穎性「物體狀態可信度 conditioned on VINS 定位品質」。**不包裝。** 未碰 VINS backend、未加 object factor、未開 G3、未改 main branch。

## 一句話 verdict
**A2 = 不 promising（leaning failed）。** 在本次資料與兩種測法下，**加入 VINS-quality features 並未穩健改善物體可信度估計**：sensor-frame 測法明確 fail；world-frame（部署傳播）測法只在部分 stratum 邊際改善 AUROC ranking，但**機率校準（NLL/ANEES/ECE）反而變差**，且正訊號被 VINS 嚴重 scale 發散 artifact 汙染。**核心賣點今晚實驗不支持。**

## 做了什麼（全部 provenance）
1. **VINS replay infra**（standalone，乾淨 baseline VINS，只 log reliability features，不設任何 weighting/injection flag，不碰 backend）：`fwvio_ws/scripts/paper2_vins_replay_one.sh` + `paper2_vins_replay_batch.sh`，config `carla_stereo_imu_640_R3_b05_gm.yaml`（640, baseline0.5, IMU-at-center, R3），IMU 經 `make_player_imu_yref.py`（proper_yref + skip-imu-head 150）。
2. **Smoke ×2 PASS**：Town01 dense scale 0.87（軌跡 sane）、Town10HD sparse scale 3.03（特徵崩潰發散=真實退化案例）；reliability csv 輸出 + timestamp 完美對齊（rel ts ↔ object gt ts 同時鐘）+ 欄位齊全。
3. **24/24 replay 成功**（100%≥70%）。scale 0.77–5.0（Town01 多近 1，Town10HD 多發散）→ 定位品質有範圍。`paper2_vins_replay_status.tsv`。
4. **Join 95.3%**（19941/20921 object 偵測對齊到最近 VINS reliability row，max_dt 0.15s）。object+VINS 雙匹配 15066 rows。`PAPER2_OBJECT_VINS_JOIN_REPORT.md`、`paper2_object_dataset_v2_with_vins.parquet`。
5. **A2 ablation ×2 測法**（4 models 同批 matched 樣本）。

## 結果（誠實數字，test set）

### Test 1 — sensor-frame object error（GT ego-comp；object 誤差不含 VINS 誤差）→ **FAILED**
| model | NLL | ANEES | ECE | AUROC | riskcov@80 |
|---|---|---|---|---|---|
| distance_only | **5.26** | **1.28** | 0.121 | 0.449 | **16.8** |
| noue_no_vins | 62.4 | 119 | 0.078 | **0.555** | 18.0 |
| noue_with_vins | 126.9 | 248 | 0.065 | 0.484 | 22.5 |
- 加 VINS features **全面變差**（NLL 62→127、AUROC 0.555→0.484、riskcov 18→22.5）。degraded stratum 同向。
- 原因：object 誤差用 GT ego-comp → 不含 VINS 誤差 → VINS quality 僅「場景難度 proxy」，而 object features（range/depth/disp_std/bbox）已直接捕捉場景難度 → VINS 冗餘。**distance-only 反而最佳校準**（ANEES 1.28）。

### Test 2 — world-frame object error（VINS ego-pose 傳播；sim3 對齊求每幀定位誤差 → 傳播）→ **WEAK/inconclusive**
world_err median 53.3m vs sensor-only 3.08m（定位加 50m，**被 VINS catastrophic 發散主導**）。
| stratum | model | NLL | AUROC | riskcov@80 |
|---|---|---|---|---|
| overall | no_vins | **21.5** | 0.586 | **82.6** |
| overall | with_vins | 32.3 | 0.586 | 91.8 |
| degraded | no_vins | **18.2** | 0.591 | **83.5** |
| degraded | with_vins | 33.8 | **0.614** | 91.3 |
- 加 VINS features：**NLL/ANEES/ECE 變差**（校準退步），只在 degraded/0-15m 的 **AUROC 邊際變好**（0.591→0.614、0.584→0.644）。per-bin：0-15m AUROC↑，但 15-30m/30m+ AUROC↓。
- 即使在「對 VINS 有利」的傳播機制下，也**沒有穩健勝出**。

## 為什麼（誠實機制，非藉口）
1. **冗餘**：object 觀測 features（range、depth、disparity variance、bbox、bearing）已編碼「這個物體估計可不可靠」的大部分資訊；VINS 定位品質對 **sensor 誤差** 是冗餘的。這與 Paper-1 的發現一致（視覺 reliability re-encode 幾何約束強度）。
2. **VINS 發散 artifact**：這些激進轉彎 640 錄製讓 VINS 常 scale 發散（0.77–5.0×）+ yaw 漂移 → world_err 被 yaw×range 的 catastrophic 值主導（median 53m），重尾打壞 Gaussian 校準，且不是真實 VINS 行為。
3. **重尾**：30m+ 物體誤差 p95 達 132m，Gaussian NLL/ANEES 在 linear space 失效；log-space/quantile loss 可能改變校準圖像（但不太可能翻成穩健勝出）。

## 對決策的意涵（交你裁示，我不自決）
- **A2 不 promising → 依規格不進 G3 backend scaffold**（已守住：未建 branch、未碰 backend）。
- 核心新穎性「conditioned on VINS quality」**目前無實證支撐**。三條路（交你選）：
  1. **方法學修正再驗**：(a) 修 VINS 發散（更溫和錄製/調 VINS/加 wheel factor 穩定 scale）讓 world-frame 傳播測法不被 artifact 汙染；(b) 真正的 world-frame re-localization（用 VINS pose 重新定位物體 + 物體 world GT，而非解析傳播模型）；(c) 重尾-aware loss。**若這些修正後 degraded bins 仍不勝，A2 基本證偽。**
  2. **承認 conditioning 冗餘、轉貢獻**：本研究最強的實證是 **G0/G1 的 raw object benchmark + phase map**（measurement contribution，已紮實），加上「VINS-quality conditioning 經嚴格測試為冗餘/弱」的**誠實負結果**（本身可發表為 insight，呼應 Paper-1）。
  3. **暫停 Paper-2 conditioning 主軸**，把資源放回 Paper-1。
- 我的誠實評估：test 1 的負結果穩健（非 artifact），test 2 的弱訊號被發散汙染 → **不足以宣稱 A2 成立**；要救活需先解 VINS 發散 + 做真 world-frame re-localization，成功機率中等偏低。

## 產物
- 報告：`PAPER2_A2_VINS_CONDITIONING_RESULTS.md`（test1+test2 全表）、`PAPER2_OBJECT_VINS_JOIN_REPORT.md`、`PAPER2_VINS_REPLAY_A2_STATUS.md`、本檔。
- 資料：`paper2_object_dataset_v2_with_vins.parquet`(15066)、`paper2_raw_object_benchmark_all_with_vins.csv`、`paper2_vins_replay_status.tsv`、`paper2_a2_metrics.csv`、`paper2_a2_worldframe_metrics.csv`。
- 模型：`outputs/paper2_a2_*/checkpoints/{noue_no_vins.pt,noue_with_vins.pt}`。
- replay 輸出：`/mnt/sata4t/ivlab3_data/fwvio/results/paper2_vins/rep_*/{vio.csv,reliability_features_vins.csv}`（24 條）。
- scripts：`paper2_vins_replay_{one,batch}.sh`、`paper2_join_vins_to_objects.py`、`paper2_a2_ablation.py`、`paper2_a2_worldframe.py`。

**STOP — A2 已裁決（不 promising，未進 G3）。等你決定上面三條路。** KITTI image_2/image_3 下載已完成（watcher 解壓中）。
