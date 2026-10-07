#!/usr/bin/env bash
# Run the 4-variant batch for several recordings, SEQUENTIALLY (no VINS contention).
WS=/home/ivlab3/fwvio_estimator_ws_wheel
set -- \
  "Town01__dynamic_v3__runmedium_b1 t01_medium_b1" \
  "Town06__dynamic_v3__rundense_b1 t06_dense_b1" \
  "Town07__dynamic_v3__rundense_b1 t07_dense_b1"
for spec in "$@"; do
  set -- $spec
  echo "########## $(date +%T) RUN $1 ##########"
  bash "$WS/scripts/paper2_vins_aware_batch.sh" "$1" "$2" 0.5 >> "$WS/paper2/track_a/multirun.log" 2>&1
done
echo "########## MULTIRUN ALL DONE $(date +%T) ##########" >> "$WS/paper2/track_a/multirun.log"
