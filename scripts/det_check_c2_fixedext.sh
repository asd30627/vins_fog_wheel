#!/usr/bin/env bash
# Step 4: THE C2 acceptance test. Run urban28 cov-OFF UNDER C2 (REL_WHEEL_PRELOAD = the 197444-sample
# dump, /wheel/delta subscription SKIPPED) 3x, pb1.0, fixedext. C2 success criterion = ALL md5 bit-identical
# (the racy baseline gave a different md5 every run). Each MUST be full (~19735 rows / span>=1970s); a
# truncated run is invalid (CARLA load spike) -> retry pb0.5. Verifies the two C2 log lines each run.
set -o pipefail
SEQ=urban28-pankyo
WS=/home/ivlab3/fwvio_estimator_ws_wheel
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
SEQROOT="$EXT/$SEQ"; GT="$SEQROOT/pose/$SEQ/global_pose.tum"
SCRATCH="/mnt/sata4t/ivlab3_data/fwvio/results/p1_wheel_v2/_work_wheel/fog/$SEQ"
VINSLOG="$SCRATCH/logs/vins.log"
OUTBASE="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/det_check_c2/$SEQ"
WHEEL_DUMP="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/v1_wheel_value/$SEQ/wheel_dump.csv"
NREP=3
mkdir -p "$OUTBASE"
source /opt/ros/jazzy/setup.bash 2>/dev/null
source "$WS/install/setup.bash" 2>/dev/null
ate_of(){ grep -iE "^\s*rmse" "$1" 2>/dev/null | awk '{print $2}'; }
sr_of(){ awk 'NR==1{f=$1}{l=$1}END{printf "%.1f %d", l-f, NR}' "$1"; }

[[ -s "$WHEEL_DUMP" ]] || { echo "[C2STEP4] FATAL: wheel dump missing: $WHEEL_DUMP"; exit 1; }
echo "[C2STEP4] binary=$(md5sum "$WS/install/vins/lib/vins/vins_node"|cut -d' ' -f1)  preload=$WHEEL_DUMP ($(($(wc -l <"$WHEEL_DUMP")-1)) samples)  pb1.0 fixedext cov-OFF C2  $(date -Iseconds)"

run_rep(){  # $1=idx $2=rate-tag -> sets RUN_SPAN; returns 0 if full
  local i="$1" tag="$2"
  local TEMPLATE="$WS/src/kaist_player/config/urban28_pankyo_fog_pb${tag}.yaml"
  local OUT="$OUTBASE/rep${i}"; mkdir -p "$OUT"
  export USE_EXPLICIT_FIXEDEXT=1
  export REL_WHEEL_PRELOAD="$WHEEL_DUMP"             # C2: deterministic wheel preload + skip /wheel/delta sub
  export REL_PERFEAT_LOG=1 REL_WHEEL_REFERENCE_ONLY=1 PUBLISH_WHEEL_TOPIC=1
  export REL_PERFEAT_CSV_PATH="$OUT/perfeat_throwaway.csv" REL_SEQUENCE_NAME="$SEQ"
  unset REL_ANISO_INFO RC_APLUS REL_USE_LEARNED_MODEL REL_ONNX_PATH
  echo "[C2STEP4] >>> rep${i} (pb${tag}) START $(date +%H:%M:%S)"
  bash "$WS/scripts/run_one_p1_baseline.sh" "$SEQ" "$SEQROOT" "$TEMPLATE" "$GT" fog > "$OUT/runner.log" 2>&1
  local rc=$?; rm -f "$OUT/perfeat_throwaway.csv"
  cp -f "$VINSLOG" "$OUT/vins.log" 2>/dev/null || true
  if [[ $rc -ne 0 || ! -s "$SCRATCH/vins_raw/vio.tum" ]]; then echo "[C2STEP4] rep${i} RUNNER FAILED rc=$rc"; tail -15 "$OUT/runner.log"; return 2; fi
  cp -f "$SCRATCH/vins_raw/vio.tum" "$OUT/vio.tum"; cp -f "$SCRATCH/metrics/ape_vio.txt" "$OUT/ape_vio.txt" 2>/dev/null || true
  read RUN_SPAN rw < <(sr_of "$OUT/vio.tum")
  local full=$(awk -v s="$RUN_SPAN" 'BEGIN{print (s>=1970.0)?1:0}')
  # verify C2 actually engaged
  local preload_line=$(grep -E "\[C2\] wheel preload: [0-9]+ samples" "$OUT/vins.log" 2>/dev/null | tail -1)
  local skip_line=$(grep -E "subscription SKIPPED" "$OUT/vins.log" 2>/dev/null | tail -1)
  echo "[C2STEP4] rep${i} (pb${tag}) DONE span=${RUN_SPAN}s rows=${rw} ate=$(ate_of "$OUT/ape_vio.txt") md5=$(md5sum "$OUT/vio.tum"|cut -d' ' -f1) full=${full}"
  echo "[C2STEP4] rep${i} C2-log: preload='${preload_line##*\] }'  skip=$([[ -n "$skip_line" ]] && echo YES || echo NO)"
  [[ "$full" -eq 1 ]] && return 0 || return 1
}

for i in $(seq 1 $NREP); do
  if ! run_rep "$i" "1p0"; then
    echo "[C2STEP4] rep${i} truncated/failed at pb1.0 -> retry pb0.5 (rule out CARLA load spike; truncation != C2 failure)"
    if ! run_rep "$i" "0p5"; then echo "[C2STEP4] rep${i} STILL not full at pb0.5 -> flag + continue (will mark invalid)"; fi
  fi
done

echo "[C2STEP4] =========== C2 RESULT: 3 full runs urban28 cov-OFF (preload, no /wheel/delta callback) ==========="
declare -a M
allfull=1
for i in $(seq 1 $NREP); do
  T="$OUTBASE/rep${i}/vio.tum"
  if [[ -s "$T" ]]; then read sp rw < <(sr_of "$T"); m=$(md5sum "$T"|cut -d' ' -f1); a=$(ate_of "$OUTBASE/rep${i}/ape_vio.txt")
    full=$(awk -v s="$sp" 'BEGIN{print (s>=1970.0)?1:0}'); [[ "$full" -ne 1 ]] && allfull=0
    echo "[C2STEP4]   rep${i}: md5=$m ate=$a span=${sp}s rows=${rw} full=${full}"; M[$i]="$m"
  else echo "[C2STEP4]   rep${i}: MISSING"; allfull=0; fi
done
bid=1; for i in $(seq 2 $NREP); do [[ "${M[$i]}" == "${M[1]}" ]] || bid=0; done
if [[ $allfull -eq 1 && $bid -eq 1 ]]; then
  echo "[C2STEP4]   VERDICT: ALL $NREP runs BIT-IDENTICAL (md5 equal) + all full -> C2 ELIMINATES the race (std=0)."
  echo "[C2STEP4]   (Stronger than isolated: CARLA was contending for CPU, yet byte-identical.)"
else
  echo "[C2STEP4]   VERDICT: NOT all bit-identical/full -> DO NOT conclude C2 failed yet; check 'full' column"
  echo "[C2STEP4]   (truncated=CARLA load spike, rerun; full-but-different=investigate C2). See per-rep above."
fi
echo "[C2STEP4] done"
