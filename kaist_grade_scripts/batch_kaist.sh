#!/usr/bin/env bash
# KAIST per-grade FOG-base baseline (Curve 1) + Probe-B FOG-off passes. Serial, isolated (CARLA off).
# NO estimator.cpp change. fog grade via GRADE env (runner fog_csv override). Outputs ATE per run.
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
WS=/home/ivlab3/fwvio_estimator_ws
TEMPLATE="$WS/src/kaist_player/config/urban28_pankyo_fog.yaml"
OUT=/mnt/sata4t/ivlab3_data/fwvio/results/p1_grade
SP=/tmp/claude-1000/-home-ivlab3-fwvio-estimator-ws-wheel/4b1d1a98-a243-46a9-9784-79394714f7cc/scratchpad
ROW=$SP/kaist_grade_rows.tsv; LOG=$SP/batch_kaist_progress.log
mkdir -p "$OUT"
[ -f "$ROW" ] || printf "seq\tgrade\tmode\trep\tate_rmse\tvio_rows\twall_s\n" > "$ROW"
cd "$WS"

run_one(){  # seq mode grade rep
  local seq="$1" mode="$2" grade="$3" rep="$4"
  local tag; [ "$mode" = imu ] && tag="fogoff" || tag="$grade"
  local dst="$OUT/$seq/${tag}_rep${rep}"; mkdir -p "$dst"
  echo "[batch] $seq / $tag / rep$rep  $(date +%H:%M:%S)" | tee -a "$LOG"
  local t0=$(date +%s)
  GRADE="$grade" USE_EXPLICIT_FIXEDEXT=1 \
    bash scripts/run_one_p1_baseline.sh "$seq" "$EXT/$seq" "$TEMPLATE" \
       "$EXT/$seq/pose/$seq/global_pose.tum" "$mode" > "$dst/runner.log" 2>&1
  local rc=$? wall=$(($(date +%s)-t0))
  local src="$OUT/../p1_factors/_work/$mode/$seq"
  cp -f "$src/vins_raw/vio.tum" "$dst/" 2>/dev/null
  cp -f "$src/vins_raw/vio_loop.tum" "$dst/" 2>/dev/null
  cp -rf "$src/metrics" "$dst/" 2>/dev/null
  cp -f "$src/logs/vins.log" "$dst/vins.log" 2>/dev/null
  local ate=$(grep -E "rmse" "$dst/metrics/ape_vio.txt" 2>/dev/null | head -1 | grep -oE "[0-9.]+" | tail -1)
  local nrow=$(wc -l < "$dst/vio.tum" 2>/dev/null || echo 0)
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$seq" "$tag" "$mode" "$rep" "${ate:-NA}" "$nrow" "$wall" >> "$ROW"
  echo "  -> rc=$rc ate=${ate:-NA} rows=$nrow wall=${wall}s" | tee -a "$LOG"
}

echo "===== PHASE 1: Probe-B FOG-off (urban28 reuses existing imu_rep0) $(date +%H:%M:%S) =====" | tee -a "$LOG"
for s in urban29-pankyo urban26-dongtan urban27-dongtan; do run_one "$s" imu "kaist_real_005" 0; done

echo "===== PHASE 2: Curve 1 — per-grade FOG-base (4 seq x 4 grade x 2 rep) $(date +%H:%M:%S) =====" | tee -a "$LOG"
for s in urban28-pankyo urban29-pankyo urban26-dongtan urban27-dongtan; do
  for g in kaist_real_005 industrial_fog precision_mems general_imu; do
    for r in 0 1; do run_one "$s" fog "$g" "$r"; done
  done
done
echo "===== BATCH DONE $(date +%H:%M:%S) =====" | tee -a "$LOG"
