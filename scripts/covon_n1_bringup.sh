#!/usr/bin/env bash
# cov-ON pipeline BRING-UP (N=1, urban28). Purpose = does the pipeline RUN: estimator loads the A+ ONNX,
# 15-dim input fed, no crash, output sane. NOT a win/lose test (N=1 can't separate signal from ~4% noise).
# cov-ON WITHOUT C2 (original /wheel/delta callback, no REL_WHEEL_PRELOAD) -> consistent with baseline, no V2 needed.
# Also dumps first-window C++ (15 inputs + a,b,c) via REL_COV_DUMP for the golden parity vs Python onnxruntime.
set -o pipefail
SEQ=urban28-pankyo
WS=/home/ivlab3/fwvio_estimator_ws_wheel
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
SEQROOT="$EXT/$SEQ"; GT="$SEQROOT/pose/$SEQ/global_pose.tum"
TEMPLATE="$WS/src/kaist_player/config/urban28_pankyo_fog_pb1p0.yaml"
SCRATCH="/mnt/sata4t/ivlab3_data/fwvio/results/p1_wheel_v2/_work_wheel/fog/$SEQ"
VINSLOG="$SCRATCH/logs/vins.log"
OUT="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/covon_n1/$SEQ"
ONNX="/home/ivlab3/dl_reliability_ws/onnx_aplus_framei/reliability_cov_aplus_F-${SEQ}.onnx"   # held-out fold for urban28
COVDUMP="$OUT/cov_dump.csv"
mkdir -p "$OUT"
source /opt/ros/jazzy/setup.bash 2>/dev/null
source "$WS/install/setup.bash" 2>/dev/null
[[ -s "$ONNX" ]] || { echo "[COVON] FATAL: ONNX missing: $ONNX"; exit 1; }

echo "[COVON] binary=$(md5sum "$WS/install/vins/lib/vins/vins_node"|cut -d' ' -f1)  onnx=$(basename "$ONNX")  cov-ON A+ callback(no-C2) fixedext pb1.0  $(date -Iseconds)"
export USE_EXPLICIT_FIXEDEXT=1
export REL_FEATURE_RELIABILITY=1 REL_ANISO_INFO=1 REL_USE_LEARNED_MODEL=1 REL_ONNX_PATH="$ONNX" RC_APLUS=1
export REL_COV_DUMP="$COVDUMP"
export REL_WHEEL_REFERENCE_ONLY=1 PUBLISH_WHEEL_TOPIC=1 REL_SEQUENCE_NAME="$SEQ"
unset REL_WHEEL_PRELOAD   # cov-ON via original callback path (no C2) -> no preload/V2 concern this pass

echo "[COVON] >>> run START $(date +%H:%M:%S)"
bash "$WS/scripts/run_one_p1_baseline.sh" "$SEQ" "$SEQROOT" "$TEMPLATE" "$GT" fog > "$OUT/runner.log" 2>&1
rc=$?
cp -f "$VINSLOG" "$OUT/vins.log" 2>/dev/null || true
echo "[COVON] runner rc=$rc"
if [[ ! -s "$SCRATCH/vins_raw/vio.tum" ]]; then echo "[COVON] NO vio.tum -> pipeline did NOT produce a trajectory (crash?)"; tail -25 "$OUT/vins.log"; exit 1; fi
cp -f "$SCRATCH/vins_raw/vio.tum" "$OUT/vio.tum"; cp -f "$SCRATCH/metrics/ape_vio.txt" "$OUT/ape_vio.txt" 2>/dev/null || true

span=$(awk 'NR==1{f=$1}{l=$1}END{printf "%.1f",l-f}' "$OUT/vio.tum"); rows=$(wc -l < "$OUT/vio.tum")
ate=$(grep -iE "^\s*rmse" "$OUT/ape_vio.txt" 2>/dev/null | awk '{print $2}')
echo "[COVON] --- pipeline result ---"
echo "[COVON] vio.tum: span=${span}s rows=${rows}  ATE_rmse=${ate:-NA}  (ATE = RUNS-evidence ONLY, NOT win/lose)"
echo "[COVON] --- cov-ON engaged? (estimator log) ---"
grep -E "reliability-cov\] ONNX ready|reliability-cov\] feats=|reliability-cov\] inference failed|ONNX load FAILED" "$OUT/vins.log" | tail -5 | sed 's/^/[COVON]   /'
echo "[COVON] --- crash/error signatures in vins.log? ---"
grep -iE "what\(\)|terminate|Segmentation|core dumped|Aborted|ERROR.*onnx|inference failed" "$OUT/vins.log" | tail -5 | sed 's/^/[COVON]   /' || true
echo "[COVON] --- C2 must be OFF (callback path) ---"
grep -E "\[C2\] wheel preload|SKIPPED" "$OUT/vins.log" >/dev/null 2>&1 && echo "[COVON]   !! UNEXPECTED C2 active" || echo "[COVON]   C2 off (callback) ✓"

echo "[COVON] ======== GOLDEN PARITY: C++ dump abc vs Python onnxruntime (same ONNX) ========"
if [[ -s "$COVDUMP" ]]; then
  /home/ivlab3/miniconda3/envs/gf/bin/python - "$COVDUMP" "$ONNX" <<'PY'
import sys, numpy as np, onnxruntime as ort
dump, onnx = sys.argv[1:3]
import csv
rows=list(csv.DictReader(open(dump)))
IN=["L00","L11","L10","logZ","disp","inv_disp","radius","logtrack","nx","ny","vx_j","vy_j","w_dx","w_dy","w_dtheta"]
X=np.array([[float(r[c]) for c in IN] for r in rows], dtype=np.float32)
abc_cpp=np.array([[float(r["a"]),float(r["b"]),float(r["c"])] for r in rows], dtype=np.float32)
s=ort.InferenceSession(onnx, providers=["CPUExecutionProvider"])
abc_py=s.run(None,{"feat":X})[0]
d=np.abs(abc_py-abc_cpp)
print(f"[COVON]   parity rows={len(rows)}  max|Δabc|={d.max():.3e}  mean|Δabc|={d.mean():.3e}")
print(f"[COVON]   sample row0: cpp={abc_cpp[0]}  py={abc_py[0]}")
print(f"[COVON]   PARITY: {'PASS (C++==Python, |Δ|<1e-4)' if d.max()<1e-4 else 'FAIL -> deployed model != trained, STOP'}")
PY
else echo "[COVON]   !! REL_COV_DUMP empty/missing ($COVDUMP) — cannot run parity"; fi
echo "[COVON] done"
