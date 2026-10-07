# PAPER2 OVERNIGHT MAX-PUSH SUMMARY (2026-06-30)

> Autonomous overnight push (Opus Max). 全程 provenance、未碰 VINS main backend、未做正式 claim、未編造。
> 紅線守住：CARLA 不穩時自動避開、A2 無資料時標 BLOCKED 不硬編、G3 backend scaffold 在 A2 未通過下 HELD。

## 1. OpenSpec 狀態
- `paper2-viwo-conditioned-noue-v4`（完整 v4 設計總綱，G0→G3）— `validate --strict` ✅ valid。
- `paper2-noue-g0-data-grounding`（G0 細節執行）— valid。
- 兩者並存，與 Paper-1 `grade-conditioned-inertial-fusion` 正交。

## 2. KITTI 狀態
- image_2 = 9.38 GB、image_3 = 3.31 GB，兩個 `wget -c` 仍在跑（鏈路慢 ~0.5MB/s，未完成）。
- label_02 / calib / oxts 三件套完整（先前確認）。
- **背景 watcher `paper2_kitti_watch_and_extract.sh`（task b8wjp9ijv）已啟動**：等兩 zip `unzip -t` 通過 → 自動解壓 + 更新 `PAPER2_KITTI_TRACKING_ASSET_STATUS.md`（最多等 6h）。**unzip/解壓 = pending（download 未完）**。KITTI tracking reader 未寫（後續）。

## 3. CARLA runs（dataset）
- **24 OK，平衡**：Town10HD ×12、Town01 ×12 = 3 densities(npc 15/40/60) × 4 spawn-indices(0/30/60/90) × 2 towns，每條 400 drive frames（560 total，640×480，aux ON），~3.2–3.5 GB/run。
- 全數通過驗證（counts_ok、per_instance 含 `type_id`+pos+bbox、n_inst 對應 npc）。status：`paper2_carla_dataset_status.tsv`。
- **⚠ 重要工程發現**：載入 **Town04 → CARLA segfault (exit 139)**；**Town02 錄製中 → CARLA SIGABRT (exit 134)**。Town10HD/Town01 零崩。→ 自動 pivot 到「Town10HD+Town01 + spawn-index route 多樣性」，避開不穩 town（符合你「town 不穩改 spawn/seed」指示）。CARLA 已 `docker stop`（錄製完成）。
- 未推到 27（你上限）：24 已平衡充足，第三 town 不穩、不值得冒崩潰風險。

## 4. Raw object benchmark（G1）
- `paper2_raw_object_benchmark_all.csv`：**20921 偵測、15811 matched**（YOLOv8m + SGBM real 深度 + ByteTrack；bearing 4° 匹配車前 GT）。
- 各 bin 充足：0-15m 1863 / 15-30m 4164 / 30m+ 9784。

| distance_bin | n | pos_err med | pos_err p95 | speed_err med | dir_err med |
|---|---|---|---|---|---|
| 0-15m | 1863 | 1.93m | 3.84m | 1.64 m/s | 5.7° |
| 15-30m | 4164 | 2.12m | 24.55m | 3.17 m/s | 17.2° |
| 30m+ | 9784 | 7.79m | 132.38m | 7.98 m/s | 65.6° |

- 趨勢單調、可解釋：raw 位置誤差隨距離暴增、p95 在 30m+ 爆（132m）；速度/方向遠距不可用。詳 `PAPER2_RAW_OBJECT_BENCHMARK.md`。

## 5. Phase map v0（`PAPER2_PHASE_MAP_V0.md`）
- pos_err median（density × distance）：距離主導；30m+ 時 density 也影響（dense 10.91m vs sparse 6.38m，遮擋/雜亂）。
- yaw 注入 lever：per-detection `e_lat ≈ r·sin(Δψ)` 已量（localization-quality 耦合軸）。

## 6. G1 gate
- **PASS**：raw 誤差量出、單調、可解釋；matched 15811≫1000；各 bin 充足；無 pipeline bug。

## 7. G2 是否完成
- **完成（object-side）**：dataset `paper2_object_dataset_v1.parquet`（15811，train 11432/val 1270/test 3109；label rates high_pos 0.52 / invalid_vel 0.60 / obs 0.55 / util 0.26）。
- 訓練 distance-only / geometry-gate / **NOUE-object**（Gaussian-NLL + invalid/obs/utility heads）/ H1。checkpoints + metrics 在 `outputs/paper2_g2_20260630_042852/`。詳 `PAPER2_NOUE_G2_RESULTS.md`。

| model | rmse | NLL | calib_err | AUROC_high | riskcov@80 |
|---|---|---|---|---|---|
| distance_only | 47.40 | **5.24** | **0.087** | 0.466 | 27.66 |
| geometry_gate | 47.41 | 584 | 0.148 | 0.494 | 31.01 |
| **noue_object** | **44.20** | 20.52 | 0.136 | **0.622** | **24.10** |

- NOUE-object heads AUROC：**observability 0.759**、invalid_velocity 0.655、utility 0.650。
- 誠實解讀：NOUE-object **勝在「可靠度排序/辨識」**（AUROC_high 0.62 vs 0.47/0.49、risk-coverage 24.1 最佳），但**絕對校準輸 distance-only**（NLL 20.5 vs 5.24；30m+ 重尾打壞 Gaussian）。→ object-only 能學到「該信哪個物體」但校準與絕對精度受限。

## 8. A2 結果（核心新穎性）
- **[2026-06-30 daytime UPDATE] A2 已解 BLOCKED 並裁決 = 不 promising（leaning failed）。** 見 `PAPER2_DAYTIME_A2_SUMMARY.md`。24/24 VINS replay 成功、join 95.3%；test1(sensor)=FAILED、test2(world 傳播)=WEAK（校準反變差，僅邊際 AUROC）。VINS-quality conditioning 對 object 可信度冗餘/弱，未進 G3。
- （原 overnight 狀態，保留紀錄）BLOCKED：CARLA dynamic_v3 是「錄製」非「VINS run」，需對 24 條跑 VINS replay。daytime 已執行。
- 今晚可達的替代對照（NOUE-object vs distance/geometry）：NOUE-object 在 AUROC/risk-coverage 勝、NLL 輸 → **inconclusive，不足以宣稱核心 A2 成立**。**核心 A2（VINS-quality conditioning 是否真的贏）仍未測。**

## 9. H1 ablation（隔離）
- H1 residual-refine（point estimate）rmse 45.57 ≈ NOUE-object 44.20 → **無改善**。維持隔離、未進主模型（正確）。checkpoint：`outputs/.../checkpoints/h1_residual.pt`。

## 10. Output policy（`PAPER2_OUTPUT_POLICY_RESULTS.md`）
- 5 級政策（full_state / high_covariance / position_only / conservative_warning）。
- **有效**：overconfident-wrong-velocity **0.586 → 0.387**（↓34%）；risk-coverage mean pos_err 29.02 → 25.10m；planner-usable ratio 0.900。

## 11. G3-lite / scaffold
- **G3-lite 離線 utility gate 完成**（`PAPER2_G3_LITE_UTILITY_GATE.md`）：feedback 候選（percentile gate）actual pos_err median 2.45m < 非候選 3.15m（gate 方向對，選到較可靠物體）；strict 絕對 gate = **0 候選**（object-only NOUE 從不夠自信 → 保守 do-no-harm）。
- **G3 backend scaffold = HELD**：A2 = BLOCKED（非 promising）→ 依規格不建 object-factor scaffold、不開 branch、不碰 estimator backend。

## 12. Blocked items
1. **A2（VINS-quality conditioning）** — 需對 24 條 CARLA recording 跑 VINS replay 產 `reliability_features_vins.csv`，才能測核心新穎性。最高優先後續。
2. **KITTI image_2/image_3 解壓** — download 未完（watcher b8wjp9ijv 等候中）。
3. **Town02/03/04 CARLA 不穩** — 載入/錄製 segfault；dataset 限 Town10HD+Town01（town 多樣性受限）。
4. **G3 backend object factor** — held pending A2 promising。
5. NOUE 絕對校準（30m+ 重尾）— 需 heavy-tail-aware loss / 分 bin 模型 / VINS 條件化改善。

## 13. 明天決策建議（不自行擴張）
1. **最高優先：解 A2**。授權對 24 條 recording 跑 VINS replay（CARLA 停、phase-separate）產 reliability_features_vins.csv → join → 真 A2（NOUE-full-with-VINS vs without）。這是全案核心新穎性的唯一裁決。
2. 若要 town 多樣性：考慮 `carlasim/carla:0.9.16-maps`（39.5GB image，可能含穩定的更多 town）或修 collect 的 load timeout；或接受 Town10HD+Town01 為主。
3. 是否補到 27 條（再 3 條）— 邊際價值低，可略。
4. KITTI：watcher 完成後做 tracking reader feasibility（真實資料備援，非主路徑）。
5. NOUE 校準改善（log-space metrics 為主、heavy-tail loss、遠距 invalid regime）。

## 產物清單（repo root / outputs / scripts）
- 報告：`PAPER2_RAW_OBJECT_BENCHMARK.md`、`PAPER2_PHASE_MAP_V0.md`、`PAPER2_NOUE_G2_RESULTS.md`、`PAPER2_OUTPUT_POLICY_RESULTS.md`、`PAPER2_G3_LITE_UTILITY_GATE.md`、`PAPER2_KITTI_TRACKING_ASSET_STATUS.md`、本檔。
- 資料：`paper2_raw_object_benchmark_all.csv`(20921)、`paper2_object_dataset_v1.parquet`(15811)、`paper2_g2_test_predictions.csv`、`paper2_g3_feedback_candidates.csv`、`paper2_carla_dataset_status.tsv`。
- 模型：`outputs/paper2_g2_20260630_042852/checkpoints/{noue_object.pt,h1_residual.pt}` + `metrics_full.json`。
- scripts：`paper2_raw_object_probe.py`、`paper2_raw_object_benchmark.py`、`paper2_build_object_dataset.py`、`paper2_noue_g2_train.py`、`paper2_output_policy.py`、`paper2_g3_lite.py`、`paper2_validate_run.py`；錄製 `fwvio_ws/scripts/{collect_carla_v2.py(+type_id), run_carla_dynamic_v3_probe.sh, paper2_carla_dataset_driver_v2.sh, paper2_carla_preload_town.py, paper2_kitti_watch_and_extract.sh}`。

**STOP — overnight push 完成。CARLA 已停，KITTI watcher + wget 續跑。等你醒來做 design checkpoint（首推：授權 VINS replay 解 A2）。**
