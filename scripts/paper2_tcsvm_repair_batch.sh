#!/usr/bin/env bash
# Phase 6 repair — controlled same-session comparison of 4 VINS mask variants on the 2 PASS_CORE runs,
# to test whether the LEARNED TCSV-M mask matches/beats the raw_speed gate (claim J repair).
# Variants: baseline | validity_aware(raw_speed) | tcsvm(learned) | oracle(gt_speed).
# Same session => same CPU state => controls the known VINS-replay nondeterminism.
# Appends to a FRESH jsonl so the original Phase-C file is untouched.
set -o pipefail
WS=/home/ivlab3/fwvio_estimator_ws_wheel
MASKDIR=/mnt/sata4t/ivlab3_data/fwvio/results/paper2_vinsaware/_masks
OUTJSONL="$WS/paper2/track_a/paper2_tcsvm_repair_vins_metrics.jsonl"
RATE=0.5
: > "$OUTJSONL"   # fresh

run_variant(){ # RUN TAG variant mask_json_or_empty
  local RUN="$1" TAG="$2" var="$3" mj="$4"
  local REC=/mnt/sata4t/datasets/carla_fwvio/$RUN
  local otag="${TAG}__${var}"
  echo "----- run=$RUN variant=$var tag=$otag $(date +%T) -----"
  if [ -n "$mj" ]; then export MASK_JSON="$mj"; else unset MASK_JSON; fi
  bash "$WS/scripts/paper2_vins_run_one.sh" "$REC" "$otag" "$RATE" > "$WS/paper2/track_a/tcsvmrep_${otag}.log" 2>&1
  unset MASK_JSON
  local od=/mnt/sata4t/ivlab3_data/fwvio/results/paper2_vinsaware/$otag
  python3 "$WS/scripts/paper2_vins_metrics.py" "$REC" "$od" "$otag" \
    | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); d['run']='$RUN'; d['variant']='$var'; d['tag']='$TAG'; print(json.dumps(d))" \
    | tee -a "$OUTJSONL"
}

for pair in "Town01__dynamic_v3__rundense_b1 t01r_dense" "Town01__dynamic_v3__runmedium_b1 t01r_medium"; do
  set -- $pair; RUN="$1"; TAG="$2"
  run_variant "$RUN" "$TAG" baseline       ""
  run_variant "$RUN" "$TAG" validity_aware "$MASKDIR/mask_${RUN}__validity_aware.json"
  run_variant "$RUN" "$TAG" tcsvm          "$MASKDIR/mask_${RUN}__tcsvm.json"
  run_variant "$RUN" "$TAG" oracle         "$MASKDIR/mask_${RUN}__oracle.json"
done
echo "===== TCSVM REPAIR BATCH DONE $(date +%T) ====="