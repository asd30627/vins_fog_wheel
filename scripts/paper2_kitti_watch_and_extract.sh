#!/usr/bin/env bash
# Paper-2 G0 (Workstream A/H) — wait for KITTI tracking image_2/image_3 downloads to finish,
# then unzip-test, extract, count files, and update the asset-status report. Background watcher.
set -uo pipefail
KR=/mnt/sata4t/datasets/kitti/tracking
WS=/home/ivlab3/fwvio_estimator_ws_wheel
REPORT="$WS/PAPER2_KITTI_TRACKING_ASSET_STATUS.md"
MAX_WAIT=21600   # 6h
POLL=300
waited=0
echo "[kitti-watch] start $(date)"
while [ $waited -lt $MAX_WAIT ]; do
  ok2=0; ok3=0
  unzip -t "$KR/data_tracking_image_2.zip" >/dev/null 2>&1 && ok2=1
  unzip -t "$KR/data_tracking_image_3.zip" >/dev/null 2>&1 && ok3=1
  if [ $ok2 -eq 1 ] && [ $ok3 -eq 1 ]; then
    echo "[kitti-watch] both zips COMPLETE at $(date); extracting ..."
    cd "$KR" || exit 1
    unzip -o -q data_tracking_image_2.zip && echo "[kitti-watch] image_2 extracted"
    unzip -o -q data_tracking_image_3.zip && echo "[kitti-watch] image_3 extracted"
    unzip -o -q data_tracking_label_2.zip 2>/dev/null
    unzip -o -q data_tracking_calib.zip 2>/dev/null
    unzip -o -q data_tracking_oxts.zip 2>/dev/null
    n2=$(find "$KR/training/image_02" -name "*.png" 2>/dev/null | wc -l)
    n3=$(find "$KR/training/image_03" -name "*.png" 2>/dev/null | wc -l)
    nseq2=$(ls -d "$KR/training/image_02"/*/ 2>/dev/null | wc -l)
    nlab=$(ls "$KR/training/label_02"/*.txt 2>/dev/null | wc -l)
    {
      echo ""
      echo "## UPDATE $(date '+%Y-%m-%d %H:%M:%S') — downloads complete + extracted (auto-watcher)"
      echo "- data_tracking_image_2.zip: unzip -t OK; extracted training/image_02/ ($nseq2 seqs, $n2 png)"
      echo "- data_tracking_image_3.zip: unzip -t OK; extracted training/image_03/ ($n3 png)"
      echo "- label_02 seqs: $nlab ; calib + oxts extracted."
      echo "- KITTI tracking now USABLE for reader-feasibility (next step, separate change)."
    } >> "$REPORT"
    echo "[kitti-watch] DONE: image_02 $n2 png ($nseq2 seqs), image_03 $n3 png, labels $nlab seqs"
    exit 0
  fi
  sleep $POLL; waited=$((waited+POLL))
done
echo "[kitti-watch] TIMEOUT after ${MAX_WAIT}s; downloads still incomplete."
{ echo ""; echo "## UPDATE $(date '+%Y-%m-%d %H:%M:%S') — watcher TIMEOUT, downloads still incomplete (image_2 $(stat -c%s "$KR/data_tracking_image_2.zip" 2>/dev/null)B, image_3 $(stat -c%s "$KR/data_tracking_image_3.zip" 2>/dev/null)B)"; } >> "$REPORT"
exit 2
