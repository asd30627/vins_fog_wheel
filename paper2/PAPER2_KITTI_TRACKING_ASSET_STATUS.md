# PAPER2_KITTI_TRACKING_ASSET_STATUS — Workstream A

> Change: paper2-noue-g0-data-grounding。狀態快照 2026-06-30 ~02:21。**下載進行中（背景），非最終狀態。**

## 來源（不自猜 URL）
- avg-kitti 官方 S3 鏡像（與既有 `kaist_grade_scripts/kitti_dl.sh` 同 bucket）：
  - `https://s3.eu-central-1.amazonaws.com/avg-kitti/data_tracking_image_2.zip`
  - `https://s3.eu-central-1.amazonaws.com/avg-kitti/data_tracking_image_3.zip`
- 目錄：`/mnt/sata4t/datasets/kitti/tracking/`

## 資產狀態表（實測）

| zip | exists | size (now) | unzip -t | extracted | file count | 完整? |
|---|---|---|---|---|---|---|
| `data_tracking_label_2.zip` | ✅ | 2.2M | OK | 尚未解壓 | 23 entries（label_02 0000–0020，21 序列）| ✅ |
| `data_tracking_calib.zip` | ✅ | 88K | OK | 尚未解壓 | 52（train21+test29）| ✅ |
| `data_tracking_oxts.zip` | ✅ | 8.0M | OK | 尚未解壓 | 52（train21+test29，30 欄含速度）| ✅ |
| `data_tracking_image_2.zip`（left）| ✅ | **6.57 GB（↑中）** | 尚未測（下載中）| ✗ | — | ⏳ **下載中** |
| `data_tracking_image_3.zip`（right）| ✅ | **0.21 GB（↑中）** | 尚未測（下載中）| ✗ | — | ⏳ **下載中** |

## 下載進度（背景 process，實測）
- **image_2**：`wget -c -q ...data_tracking_image_2.zip`，**PID 25596**（前一 session 啟動的可續傳 wget，已跑 ~5h13m，檔案 5.7G→6.57G 持續成長）。**決策：不 mv、不重啟**——它正在 `wget -c` 續傳中，mv 會打斷正在被寫入的檔；讓既有可續傳下載完成即可（這已是 task 要的可續傳作法）。
- **image_3**：`wget -c ...data_tracking_image_3.zip`，**PID 480480**（本次新起，log `download_image3.log`）。鏈路極慢（log 顯示 ~150K/s，ETA ~11h；與 raw_data 多個下載搶頻寬）。
- log：`/mnt/sata4t/datasets/kitti/tracking/download.log`（image_2，舊）、`/mnt/sata4t/datasets/kitti/tracking/download_image3.log`（image_3，本次）。

## 待完成（下載結束後，本 change 範圍內）
- [ ] A4：`unzip -t data_tracking_image_{2,3}.zip`（完整性）+ `unzip -l | tail`
- [ ] A5：解壓出 `training/image_02/`、`training/image_03/`，列檔數，對齊 label_02/calib/oxts 的 21 train 序列
- **不做**（後續 change）：KITTI tracking 的 VINS reader（現有 `kitti_gps_test`/`kitti_odom_test` 吃 raw/odom 佈局，非 tracking `image_02/03`）。

## 風險
- 鏈路 ~0.15–0.7 MB/s 且多下載搶頻寬 → image_2/image_3 完成時間數小時級，不確定。
- 完成前無法做 unzip 完整性與解壓；本報告為進行中快照。

## UPDATE 2026-06-30 11:33:06 — watcher TIMEOUT, downloads still incomplete (image_2 15813146295B, image_3 16559331033B)

## UPDATE 2026-06-30 (daytime) — zips COMPLETE + extracted for validation
- data_tracking_image_2.zip: **complete** (15.8GB, 19155 files, `unzip -l` OK) → extracting `training/image_02/` (background).
- data_tracking_image_3.zip: **complete** (18.3GB, 19155 files) → extracting `training/image_03/`.
- data_tracking_label_2.zip: extracted → `training/label_02/` (21 train seqs 0000–0020).
- data_tracking_calib.zip: extracted → `training/calib/` (fx=721.54, cx=609.56, cy=172.85, stereo baseline≈0.53 m from P2/P3).
- data_tracking_oxts.zip: extracted → `training/oxts/` (30 cols; vf=col9 forward vel, yaw=col6 → ego-motion comp).
- label_02 schema (per row): frame, track_id, type, trunc, occ, alpha, bbox2d(x1,y1,x2,y2), dims(h,w,l), **loc3d(x,y,z camera)**, rot_y.
- → **enough for a FULL position+velocity validity replication** (GT 3D position + 2D bbox + track_id; velocity via cross-frame GT-position differencing + oxts ego-comp). Not a weak-only validation.

## UPDATE 2026-06-30 (validation) — image_03 CORRUPT; monocular path used
- **data_tracking_image_3.zip (right) = CORRUPTED**: 18.3GB (>image_2 15.8GB, abnormal). `unzip -l` reads central
  dir (19155 files) but extraction fails — unzip "overlapped components / zip bomb", python zipfile "Bad magic
  number"; per-member salvage = **0/21 sequences** extractable. Likely a wget -c resume corruption.
- → **stereo unavailable**. Validation used **monocular bbox-height depth** on image_02 (left, fully extracted, 21 seqs).
- image_02 (left): OK, 21 seqs extracted. label_02/calib/oxts: OK.
- If stereo is wanted later: rm the corrupt zip + clean re-download data_tracking_image_3.zip (~hours on the link).

## UPDATE 2026-06-30 17:45:18 — downloads complete + extracted (auto-watcher)
- data_tracking_image_2.zip: unzip -t OK; extracted training/image_02/ (21 seqs, 8008 png)
- data_tracking_image_3.zip: unzip -t OK; extracted training/image_03/ (8008 png)
- label_02 seqs: 21 ; calib + oxts extracted.
- KITTI tracking now USABLE for reader-feasibility (next step, separate change).
