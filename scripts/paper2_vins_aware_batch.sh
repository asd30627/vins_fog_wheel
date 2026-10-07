#!/usr/bin/env bash
# Paper-2 Part 2 Phase B+C — for ONE recording, run 4 VINS variants SEQUENTIALLY (single VINS node,
# no CPU contention) and collect robust metrics:
#   baseline | all_dynamic(mask all det) | validity_aware(mask raw_speed>1) | oracle(mask gt_speed>1)
#   usage: paper2_vins_aware_batch.sh <run_stem> <short_tag> [rate]
# Appends JSON metrics lines to paper2/track_a/paper2_validity_aware_vins_metrics.jsonl
set -o pipefail
RUN="${1:?run stem e.g. Town01__dynamic_v3__rundense_b1}"; TAG="${2:?short tag}"; RATE="${3:-0.5}"
WS=/home/ivlab3/fwvio_estimator_ws_wheel
REC=/mnt/sata4t/datasets/carla_fwvio/$RUN
MASKDIR=/mnt/sata4t/ivlab3_data/fwvio/results/paper2_vinsaware/_masks
OUTJSONL="$WS/paper2/track_a/paper2_validity_aware_vins_metrics.jsonl"
mkdir -p "$MASKDIR"

echo "===== BATCH $RUN ($TAG) rate=$RATE $(date +%T) ====="
# masks (deployable + oracle)
python3 "$WS/scripts/paper2_make_vins_masks.py" --run "$RUN" --out-dir "$MASKDIR" 2>&1 | sed 's/^/[mask] /'

run_variant(){ # variant_name  mask_json_or_empty
  local var="$1" mj="$2"
  local otag="${TAG}__${var}"
  echo "----- variant=$var tag=$otag $(date +%T) -----"
  if [ -n "$mj" ]; then export MASK_JSON="$mj"; else unset MASK_JSON; fi
  bash "$WS/scripts/paper2_vins_run_one.sh" "$REC" "$otag" "$RATE" > "$WS/paper2/track_a/vinsaware_${otag}.log" 2>&1
  unset MASK_JSON
  local od=/mnt/sata4t/ivlab3_data/fwvio/results/paper2_vinsaware/$otag
  # robust metrics -> jsonl (inject run/variant)
  python3 "$WS/scripts/paper2_vins_metrics.py" "$REC" "$od" "$otag" \
    | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); d['run']='$RUN'; d['variant']='$var'; d['tag']='$TAG'; print(json.dumps(d))" \
    | tee -a "$OUTJSONL"
}

run_variant baseline ""
run_variant all_dynamic    "$MASKDIR/mask_${RUN}__all_dynamic.json"
run_variant validity_aware "$MASKDIR/mask_${RUN}__validity_aware.json"
run_variant oracle         "$MASKDIR/mask_${RUN}__oracle.json"
echo "===== BATCH DONE $RUN $(date +%T) ====="
