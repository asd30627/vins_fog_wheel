#!/usr/bin/env bash
# R3/R4: per-det YOLO probe + quality audit for the re-recorded dynamic_v3fix runs. Appends to the
# results CSV and classifies. Args: list of "Town__dynamic_v3fix__run<name>" run dir names.
GF=/home/ivlab3/miniconda3/envs/gf/bin/python
WS=/home/ivlab3/fwvio_estimator_ws_wheel
DS=/mnt/sata4t/datasets/carla_fwvio
PD=$WS/outputs/paper2_perdet_v2
CSV=$WS/paper2/track_a/paper2_carla_rerecord_results_v2.csv
mkdir -p "$PD"; rm -f "$CSV"
for run in "$@"; do
  REC="$DS/$run"
  [ -d "$REC" ] || { echo "[audit] MISSING $run"; continue; }
  T=$(echo "$run" | cut -d_ -f1)
  $GF "$WS/scripts/paper2_raw_object_probe.py" --rec "$REC" --out-csv "$PD/$run.csv" --town "$T" --density x --run "$run" > "/tmp/probe_$run.log" 2>&1
  det=$(grep -oE "det=[0-9]+" "/tmp/probe_$run.log" | head -1)
  python3 "$WS/scripts/paper2_carla_rerecord_preview_audit.py" --rec "$REC" --perdet "$PD/$run.csv" --out-csv "$CSV" --setting "$run" 2>&1 | head -1
done
echo "=== RESULTS ==="
column -t -s, "$CSV" 2>/dev/null | cut -c1-40
echo "AUDIT_BATCH_DONE"
