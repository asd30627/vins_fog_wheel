#!/usr/bin/env bash
# Reproducibility diagnostic + baseline brick 1: same new binary (e7e5575), fixedext (default),
# cov-OFF, pb 1.0, STRICT isolation (one VINS at a time). Run urban28 TWO more times (rep2, rep3);
# combined with the existing verify run (rep1 = ATE 16.16) = 3 full samples. Each MUST be full
# (~19735 rows / ~1973 s); a truncated run is flagged, not accepted. Reports 3 ATEs + md5 side by side.
set -o pipefail
SEQ=urban28-pankyo
WS=/home/ivlab3/fwvio_estimator_ws_wheel
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
SEQROOT="$EXT/$SEQ"; GT="$SEQROOT/pose/$SEQ/global_pose.tum"
TEMPLATE="$WS/src/kaist_player/config/urban28_pankyo_fog_pb1p0.yaml"
SCRATCH="/mnt/sata4t/ivlab3_data/fwvio/results/p1_wheel_v2/_work_wheel/fog/$SEQ"
VBASE="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/verify_fixedext/$SEQ"
R1_TUM="$VBASE/vio.tum"; R1_APE="$VBASE/ape_vio.txt"   # existing rep1 (16.16)
BASELINE="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/pretask1_perfeat/$SEQ/vio.tum"  # dd8d1e0 18.82
source /opt/ros/jazzy/setup.bash 2>/dev/null
source "$WS/install/setup.bash" 2>/dev/null
ate_of(){ grep -iE "^\s*rmse" "$1" 2>/dev/null | awk '{print $2}'; }
sr_of(){ awk 'NR==1{f=$1}{l=$1}END{printf "%.1f %d", l-f, NR}' "$1"; }

echo "[REPRO] binary=$(md5sum "$WS/install/vins/lib/vins/vins_node"|cut -d' ' -f1)  pb1.0 fixedext cov-OFF isolated  $(date -Iseconds)"

for i in 2 3; do
  OUT="$VBASE/rep${i}"; mkdir -p "$OUT"
  export USE_EXPLICIT_FIXEDEXT=1
  export REL_PERFEAT_LOG=1 REL_WHEEL_REFERENCE_ONLY=1 PUBLISH_WHEEL_TOPIC=1
  export REL_PERFEAT_CSV_PATH="$OUT/perfeat_throwaway.csv" REL_SEQUENCE_NAME="$SEQ"
  unset REL_ANISO_INFO RC_APLUS REL_USE_LEARNED_MODEL REL_ONNX_PATH
  echo "[REPRO] >>> rep${i} START $(date +%H:%M:%S)"
  bash "$WS/scripts/run_one_p1_baseline.sh" "$SEQ" "$SEQROOT" "$TEMPLATE" "$GT" fog > "$OUT/runner.log" 2>&1
  rc=$?; rm -f "$OUT/perfeat_throwaway.csv"
  if [[ $rc -ne 0 || ! -s "$SCRATCH/vins_raw/vio.tum" ]]; then echo "[REPRO] rep${i} RUNNER FAILED rc=$rc"; tail -15 "$OUT/runner.log"; exit 1; fi
  cp -f "$SCRATCH/vins_raw/vio.tum" "$OUT/vio.tum"; cp -f "$SCRATCH/metrics/ape_vio.txt" "$OUT/ape_vio.txt" 2>/dev/null || true
  read sp rw < <(sr_of "$OUT/vio.tum")
  full=$(awk -v s="$sp" 'BEGIN{print (s>=1970.0)?1:0}')
  echo "[REPRO] rep${i} DONE span=${sp}s rows=${rw} ate=$(ate_of "$OUT/ape_vio.txt") md5=$(md5sum "$OUT/vio.tum"|cut -d' ' -f1) full=${full}"
  [[ "$full" -ne 1 ]] && echo "[REPRO] rep${i} TRUNCATED (span ${sp}s < 1970s) — flag, not accepted (locked protocol: drop to pb0.5)"
done

echo "[REPRO] =========== 3 FULL SAMPLES (urban28 cov-OFF, fixedext, pb1.0, isolated) ==========="
R1A=$(ate_of "$R1_APE"); R2A=$(ate_of "$VBASE/rep2/ape_vio.txt"); R3A=$(ate_of "$VBASE/rep3/ape_vio.txt")
M1=$(md5sum "$R1_TUM"|cut -d' ' -f1); M2=$(md5sum "$VBASE/rep2/vio.tum"|cut -d' ' -f1); M3=$(md5sum "$VBASE/rep3/vio.tum"|cut -d' ' -f1)
echo "[REPRO]   rep1 ATE=${R1A}  md5=${M1}"
echo "[REPRO]   rep2 ATE=${R2A}  md5=${M2}"
echo "[REPRO]   rep3 ATE=${R3A}  md5=${M3}"
echo "[REPRO]   (dd8d1e0 baseline ATE=18.82  md5=$(md5sum "$BASELINE"|cut -d' ' -f1))"
bid=1; cmp -s "$R1_TUM" "$VBASE/rep2/vio.tum" || bid=0; cmp -s "$R1_TUM" "$VBASE/rep3/vio.tum" || bid=0
[[ $bid -eq 1 ]] && echo "[REPRO]   rep1==rep2==rep3 BIT-IDENTICAL (deterministic)" || echo "[REPRO]   reps NOT bit-identical (see ATE spread)"
/home/ivlab3/miniconda3/envs/gf/bin/python - "$R1A" "$R2A" "$R3A" <<'PY' 2>/dev/null
import sys
v=[float(x) for x in sys.argv[1:4]]
import statistics as st
print(f"[REPRO]   ATE: min={min(v):.3f} max={max(v):.3f} median={st.median(v):.3f} spread={max(v)-min(v):.3f}m ({(max(v)-min(v))/st.median(v)*100:.1f}% of median)")
PY
echo "[REPRO] done"
