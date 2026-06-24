#!/usr/bin/env bash
# DIAGNOSTIC ONLY (user-approved 2026-06-24): urban39 at pb3.0, 3 reps, to probe the
# pb1.0 truncation / run-to-run completion nondeterminism seen in the official baseline.
# ⚠ pb3 numbers are NOT same-basis as the 7 pb1.0 sequences -> they DO NOT enter the
# trend datapoint (spec L134). urban39's official baseline stays pb1.0.
# Differences vs phase1_baseline.sh (deliberate, for diagnosis):
#   - writes to a SEPARATE diag dir (does NOT touch official OUTBASE/urban39 rep1 pb1.0 full).
#   - NO pb0.5 retry on truncation (we WANT to capture the pb3 outcome as-is).
#   - copies vins.log per rep BEFORE the next rep overwrites it (preserve crash cause).
# Same env basis otherwise: gate binary 15a57897, wheel topic ON, wheel factor OFF,
# DL cov OFF, callback (no C2), fixedext, CARLA off. RAW only, no judgment.
set -o pipefail
SEQ=urban39-pankyo
WS=/home/ivlab3/fwvio_estimator_ws_wheel
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
SEQROOT="$EXT/$SEQ"; GT="$SEQROOT/pose/$SEQ/global_pose.tum"
TEMPLATE="$WS/src/kaist_player/config/urban28_pankyo_fog_pb3p0.yaml"
SCRATCH="/mnt/sata4t/ivlab3_data/fwvio/results/p1_wheel_v2/_work_wheel/fog/$SEQ"
DIAG="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/phase1_diag_urban39_pb3"
mkdir -p "$DIAG"
source /opt/ros/jazzy/setup.bash 2>/dev/null
source "$WS/install/setup.bash" 2>/dev/null
ate_of(){ grep -iE "^\s*rmse" "$1" 2>/dev/null | awk '{print $2}'; }

# CARLA-off guard (Decision 10 isolation precondition)
if docker ps --format '{{.Image}}' 2>/dev/null | grep -qi carla \
   || pgrep -x CarlaUE4-Linux-Shipping >/dev/null 2>&1; then
  echo "[DIAG39] FATAL: CARLA running -> not isolated. Stop."; exit 9; fi

gt_last=$(awk 'END{print $1}' "$GT")
echo "[DIAG39] ===== urban39 pb3.0 DIAGNOSTIC (3 reps, NOT a baseline) START $(date -Iseconds) ====="
echo "[DIAG39] binary=$(md5sum "$WS/install/vins/lib/vins/vins_node"|cut -d' ' -f1)  pb3.0  gt_last=$gt_last  gt_span=$(awk 'NR==1{f=$1}END{printf "%.1f",$1-f}' "$GT")s"

for i in 1 2 3; do
  OUT="$DIAG/rep${i}"; mkdir -p "$OUT"
  export USE_EXPLICIT_FIXEDEXT=1
  export REL_WHEEL_REFERENCE_ONLY=1 PUBLISH_WHEEL_TOPIC=1 REL_SEQUENCE_NAME="$SEQ"
  unset REL_ANISO_INFO RC_APLUS REL_USE_LEARNED_MODEL REL_ONNX_PATH REL_WHEEL_PRELOAD \
        REL_PERFEAT_LOG REL_COV_DUMP REL_FEATURE_RELIABILITY REL_PERFEAT_CSV_PATH
  echo "[DIAG39] >>> rep${i} (pb3.0) START $(date +%H:%M:%S)"
  bash "$WS/scripts/run_one_p1_baseline.sh" "$SEQ" "$SEQROOT" "$TEMPLATE" "$GT" fog > "$OUT/runner.log" 2>&1
  rc=$?
  # preserve artifacts per rep (vins.log/vio.tum get overwritten by the next rep)
  cp -f "$SCRATCH/vins_raw/vio.tum" "$OUT/vio.tum" 2>/dev/null || true
  cp -f "$SCRATCH/metrics/ape_vio.txt" "$OUT/ape_vio.txt" 2>/dev/null || true
  cp -f "$SCRATCH/logs/vins.log" "$OUT/vins.log" 2>/dev/null || true
  if [[ ! -s "$OUT/vio.tum" ]]; then echo "[DIAG39] rep${i} NO vio.tum (rc=$rc) -- runner tail:"; tail -8 "$OUT/runner.log"; continue; fi
  rows=$(wc -l < "$OUT/vio.tum")
  vio_last=$(awk 'END{print $1}' "$OUT/vio.tum")
  span=$(awk 'NR==1{f=$1}END{printf "%.1f",$1-f}' "$OUT/vio.tum")
  full=$(awk -v v="$vio_last" -v g="$gt_last" 'BEGIN{print (g>0 && v >= g-10.0)?1:0}')
  md5=$(md5sum "$OUT/vio.tum"|cut -d' ' -f1)
  ate=$(ate_of "$OUT/ape_vio.txt")
  echo "[DIAG39] rep${i} (pb3.0) DONE rc=$rc span=${span}s rows=${rows} vio_last=${vio_last} gt_last=${gt_last} full=${full} md5=${md5} ate=${ate} $([[ $full -eq 0 ]] && echo '<<< TRUNCATED (ate not comparable)')"
done
echo "[DIAG39] ===== done $(date -Iseconds) ====="
echo "[DIAG39] NOTE: pb3 != pb1.0 basis -> these numbers are diagnostic only, NOT the urban39 trend datapoint."
