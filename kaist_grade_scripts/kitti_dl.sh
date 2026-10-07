#!/usr/bin/env bash
# Resumable download of the two KITTI raw drives needed for odom seq05 + seq00 (with OXTS IMU).
# seq05 = 2011_09_30_drive_0018 (10.5GB), seq00 = 2011_10_03_drive_0027 (17.1GB). ~0.42MB/s link.
KR=/mnt/sata4t/datasets/kitti/raw
cd "$KR" || exit 1
BASE=https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data
dl(){ # name expected_bytes
  local n="$1" exp="$2" f="${1}_sync.zip"   # real S3 key has the _sync suffix
  echo "=== $n (expect $exp B) $(date +%H:%M:%S) ==="
  for try in $(seq 1 40); do
    curl -s -C - -o "$f" -w "  try$try: now %{size_download}B total\n" "$BASE/$n/$f"
    have=$(stat -c%s "$f" 2>/dev/null || echo 0)
    if [ "$have" -ge "$exp" ]; then echo "  COMPLETE $n ($have B)"; return 0; fi
    echo "  partial $have/$exp, resume in 5s"; sleep 5
  done
  echo "  GAVEUP $n at $(stat -c%s "$f" 2>/dev/null)B"; return 1
}
dl 2011_09_30_drive_0018 11320688364   # seq05 first (smaller)
echo "===== KITTI_SEQ05_DONE $(date +%H:%M:%S) ====="
dl 2011_10_03_drive_0027 18349607637   # seq00
echo "===== KITTI_DL_ALL_DONE $(date +%H:%M:%S) ====="
