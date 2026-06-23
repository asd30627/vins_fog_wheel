#!/usr/bin/env bash
# Phase 1: multi-rep WHEEL-ON cov-OFF baseline (the fair arm cov-ON is compared against).
# Usage: phase1_baseline.sh <SEQ> <NREP>
# Wheel state (matches cov-ON exactly EXCEPT DL cov): wheel topic ON (PUBLISH_WHEEL_TOPIC + REL_WHEEL_REFERENCE_ONLY),
# wheel factor OFF (WHEEL_FACTOR_ENABLE default 0), DL cov OFF (NO REL_ANISO_INFO/REL_USE_LEARNED_MODEL/ONNX/RC_APLUS).
# CLEAN: no REL_PERFEAT_LOG (training logger), no REL_COV_DUMP, no REL_WHEEL_PRELOAD. fixedext, pb1.0, callback path.
# Each rep MUST be full (~19735 rows / span>=1970s); truncated -> retry pb0.5. Reports N ATEs + median + range%.
# DOES NOT judge win / baseline-stability -- raw table only (user judges).
set -o pipefail
SEQ="$1"; NREP="${2:-3}"
[[ -z "$SEQ" ]] && { echo "usage: $0 <SEQ> <NREP>"; exit 2; }
WS=/home/ivlab3/fwvio_estimator_ws_wheel
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
SEQROOT="$EXT/$SEQ"; GT="$SEQROOT/pose/$SEQ/global_pose.tum"
SCRATCH="/mnt/sata4t/ivlab3_data/fwvio/results/p1_wheel_v2/_work_wheel/fog/$SEQ"
OUTBASE="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/phase1_baseline/$SEQ"
mkdir -p "$OUTBASE"
source /opt/ros/jazzy/setup.bash 2>/dev/null
source "$WS/install/setup.bash" 2>/dev/null
ate_of(){ grep -iE "^\s*rmse" "$1" 2>/dev/null | awk '{print $2}'; }
sr_of(){ awk 'NR==1{f=$1}{l=$1}END{printf "%.1f %d", l-f, NR}' "$1"; }

# CARLA-off guard (isolation). Use docker (authoritative; CARLA is containerized) + the exact binary
# name -- NOT a loose `pgrep -f CarlaUE4` which false-matches shell commands containing the string.
if docker ps --format '{{.Image}}' 2>/dev/null | grep -qi carla \
   || pgrep -x CarlaUE4-Linux-Shipping >/dev/null 2>&1; then
  echo "[P1BASE] FATAL: CARLA running (docker/binary) -> not isolated. Stop CARLA first."; exit 9; fi
echo "[P1BASE] $SEQ N=$NREP  binary=$(md5sum "$WS/install/vins/lib/vins/vins_node"|cut -d' ' -f1)  wheel-on cov-OFF callback fixedext pb1.0 (DL OFF, no perfeat-log)  $(date -Iseconds)"

run_rep(){  # $1=idx $2=rate-tag -> sets RUN_SPAN; returns 0 if full
  local i="$1" tag="$2"
  local TEMPLATE="$WS/src/kaist_player/config/urban28_pankyo_fog_pb${tag}.yaml"   # harness substitutes seq placeholders
  local OUT="$OUTBASE/rep${i}"; mkdir -p "$OUT"
  export USE_EXPLICIT_FIXEDEXT=1
  export REL_WHEEL_REFERENCE_ONLY=1 PUBLISH_WHEEL_TOPIC=1 REL_SEQUENCE_NAME="$SEQ"
  unset REL_ANISO_INFO RC_APLUS REL_USE_LEARNED_MODEL REL_ONNX_PATH REL_WHEEL_PRELOAD \
        REL_PERFEAT_LOG REL_COV_DUMP REL_FEATURE_RELIABILITY REL_PERFEAT_CSV_PATH
  echo "[P1BASE] >>> $SEQ rep${i} (pb${tag}) START $(date +%H:%M:%S)"
  bash "$WS/scripts/run_one_p1_baseline.sh" "$SEQ" "$SEQROOT" "$TEMPLATE" "$GT" fog > "$OUT/runner.log" 2>&1
  local rc=$?
  if [[ $rc -ne 0 || ! -s "$SCRATCH/vins_raw/vio.tum" ]]; then echo "[P1BASE] $SEQ rep${i} RUNNER FAILED rc=$rc"; tail -15 "$OUT/runner.log"; return 2; fi
  cp -f "$SCRATCH/vins_raw/vio.tum" "$OUT/vio.tum"; cp -f "$SCRATCH/metrics/ape_vio.txt" "$OUT/ape_vio.txt" 2>/dev/null || true
  read RUN_SPAN rw < <(sr_of "$OUT/vio.tum")
  local full=$(awk -v s="$RUN_SPAN" 'BEGIN{print (s>=1970.0)?1:0}')
  echo "[P1BASE] $SEQ rep${i} (pb${tag}) DONE span=${RUN_SPAN}s rows=${rw} ate=$(ate_of "$OUT/ape_vio.txt") md5=$(md5sum "$OUT/vio.tum"|cut -d' ' -f1) full=${full}"
  [[ "$full" -eq 1 ]] && return 0 || return 1
}

for i in $(seq 1 "$NREP"); do
  if ! run_rep "$i" "1p0"; then
    echo "[P1BASE] $SEQ rep${i} truncated/failed at pb1.0 -> retry pb0.5"
    if ! run_rep "$i" "0p5"; then echo "[P1BASE] $SEQ rep${i} STILL not full at pb0.5 -> ABORT"; exit 1; fi
  fi
done

echo "[P1BASE] ===== $SEQ RAW TABLE ($NREP reps, wheel-on cov-OFF) ====="
ATES=(); for i in $(seq 1 "$NREP"); do a=$(ate_of "$OUTBASE/rep${i}/ape_vio.txt"); ATES+=("$a"); echo "[P1BASE]   $SEQ rep${i} ATE=$a"; done
/home/ivlab3/miniconda3/envs/gf/bin/python - "$SEQ" "${ATES[@]}" <<'PY'
import sys, statistics as st
seq=sys.argv[1]; v=[float(x) for x in sys.argv[2:]]
md=st.median(v); rng=max(v)-min(v)
print(f"[P1BASE]   {seq}: N={len(v)} ATEs={['%.3f'%x for x in v]} median={md:.3f} min={min(v):.3f} max={max(v):.3f} range={rng:.3f}m ({rng/md*100:.2f}% of median)")
print(f"[P1BASE]   {seq}: (RAW — no win/stability judgment; user judges. Escalation flags for user: range>5% / range>15-20%)")
PY
echo "[P1BASE] $SEQ done"
