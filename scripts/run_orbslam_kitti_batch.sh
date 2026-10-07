#!/usr/bin/env bash
# ORB-SLAM3 STEREO baseline across KITTI Tracking sequences. GT from oxts. ATE via evo (SE3 + Sim3).
set -o pipefail
WS=/home/ivlab3/fwvio_estimator_ws_wheel
KITTI=/mnt/sata4t/datasets/kitti/tracking/training
EVO=/home/ivlab3/.local/bin/evo_ape
OUT=$WS/logs/phase6/phase6_orbslam3_kitti.csv
LOG=$WS/logs/phase6/orbslam_kitti_batch.log
echo "seq,frames,path_m,rmse_se3_m,median_se3_m,rmse_sim3_m,poses,resets" > "$OUT"
cd "$WS"
for SEQ in 0000 0004 0005 0009; do
  echo "===== KITTI $SEQ $(date +%T) =====" | tee -a "$LOG"
  gt="$WS/logs/phase6/kitti_gt_${SEQ}.tum"
  python3 "$WS/scripts/kitti_oxts_to_tum.py" --oxts "$KITTI/oxts/${SEQ}.txt" --out "$gt" >> "$LOG" 2>&1
  bash "$WS/scripts/run_orbslam_kitti_stereo.sh" "$SEQ" >> "$LOG" 2>&1
  pkill -9 -f "lib/orbslam3/stereo" 2>/dev/null; pkill -9 -f "orbslam3 stereo" 2>/dev/null; sleep 2
  tum="$WS/logs/phase6/orbslam_kitti_${SEQ}.tum"
  frames=$(ls "$KITTI/image_02/${SEQ}/"*.png 2>/dev/null | wc -l)
  poses=$(wc -l < "$tum" 2>/dev/null || echo 0)
  resets=$(grep -c "Reseting" "$WS/logs/phase6/orbslam_kitti_${SEQ}.log" 2>/dev/null)
  rmse=$($EVO tum "$gt" "$tum" -a 2>/dev/null | awk '/rmse/{print $2}')
  med=$($EVO tum "$gt" "$tum" -a 2>/dev/null | awk '/median/{print $2}')
  rmse_s=$($EVO tum "$gt" "$tum" -as 2>/dev/null | awk '/rmse/{print $2}')
  plen=$(python3 -c "import math;L=[l.split() for l in open('$KITTI/oxts/${SEQ}.txt') if l.strip()];lat0=float(L[0][0]);sc=math.cos(lat0*math.pi/180);ER=6378137.0;pts=[(sc*float(c[1])*math.pi*ER/180,sc*ER*math.log(math.tan((90+float(c[0]))*math.pi/360))) for c in L];print(round(sum(math.dist(a,b) for a,b in zip(pts,pts[1:]))))")
  echo "$SEQ,$frames,$plen,${rmse:-NA},${med:-NA},${rmse_s:-NA},$poses,$resets" | tee -a "$OUT"
done
echo "===== KITTI BATCH DONE $(date +%T) =====" | tee -a "$LOG"