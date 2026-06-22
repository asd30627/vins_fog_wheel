#!/usr/bin/env bash
# Clean wheel-on determinism check (task 1.4 / site-d bit-inv resolution).
# HARD CONDITIONS (locked by user, do not change):
#  - playback_rate 1.0 (drop to 0.5 only if a run truncates)
#  - strict isolation: ONE VINS at a time, sequential, nothing else heavy running
#  - completion precondition: each run MUST be FULL (~19735 rows / span >= 1970 s). Truncated => invalid, escalate rate.
# Same binary, cov-OFF (no REL_ANISO_INFO / RC_APLUS), wheel-on env identical to the dd8d1e0 baseline.
set -o pipefail   # NOT -u: `set -u` + `source ros setup.bash` aborts (ROS setup references unset vars)
SEQ=urban28-pankyo
WS=/home/ivlab3/fwvio_estimator_ws_wheel
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
SEQROOT="$EXT/$SEQ"; GT="$SEQROOT/pose/$SEQ/global_pose.tum"
SCRATCH="/mnt/sata4t/ivlab3_data/fwvio/results/p1_wheel_v2/_work_wheel/fog/$SEQ"
OUTBASE="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/det_check_pb/$SEQ"
BASELINE="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/pretask1_perfeat/$SEQ/vio.tum"
VINS_BIN="$WS/install/vins/lib/vins/vins_node"
FULL_SPAN_MIN=1970.0
mkdir -p "$OUTBASE"
source /opt/ros/jazzy/setup.bash 2>/dev/null
source "$WS/install/setup.bash" 2>/dev/null

BIN_MD5=$(md5sum "$VINS_BIN" | cut -d' ' -f1)
echo "[DET] binary_md5=$BIN_MD5  baseline=ab166defd845(dd8d1e0)  $(date -Iseconds)"

span_rows () { awk 'NR==1{f=$1} {l=$1} END{printf "%.1f %d", (l-f), NR}' "$1"; }

run_once () {  # $1=rate-tag(1p0/0p5) $2=idx -> sets RUN_SPAN RUN_ROWS, copies vio.tum to OUTDIR
  local tag="$1" idx="$2"
  local TEMPLATE="$WS/src/kaist_player/config/urban28_pankyo_fog_pb${tag}.yaml"
  local OUTDIR="$OUTBASE/pb${tag}_r${idx}"; mkdir -p "$OUTDIR"
  export USE_EXPLICIT_FIXEDEXT=1   # MUST use per-seq fixedext extrinsic (the missing export caused the 632m blowup)
  export REL_PERFEAT_LOG=1 REL_WHEEL_REFERENCE_ONLY=1 PUBLISH_WHEEL_TOPIC=1
  export REL_PERFEAT_CSV_PATH="$OUTDIR/perfeat_throwaway.csv" REL_SEQUENCE_NAME="$SEQ"
  unset REL_ANISO_INFO RC_APLUS REL_USE_LEARNED_MODEL REL_ONNX_PATH
  echo "[DET] >>> pb${tag} run${idx} START $(date +%H:%M:%S)"
  bash "$WS/scripts/run_one_p1_baseline.sh" "$SEQ" "$SEQROOT" "$TEMPLATE" "$GT" fog > "$OUTDIR/runner.log" 2>&1
  local rc=$?
  rm -f "$REL_PERFEAT_CSV_PATH"
  if [[ $rc -ne 0 || ! -s "$SCRATCH/vins_raw/vio.tum" ]]; then
    echo "[DET] pb${tag} run${idx} RUNNER FAILED rc=$rc"; tail -15 "$OUTDIR/runner.log"; RUN_SPAN=-1; RUN_ROWS=0; return 1
  fi
  cp -f "$SCRATCH/vins_raw/vio.tum" "$OUTDIR/vio.tum"
  cp -f "$SCRATCH/metrics/ape_vio.txt" "$OUTDIR/ape_vio.txt" 2>/dev/null || true
  read RUN_SPAN RUN_ROWS < <(span_rows "$OUTDIR/vio.tum")
  local ate=$(grep -iE "^\s*rmse" "$OUTDIR/ape_vio.txt" 2>/dev/null | awk '{print $2}')
  echo "[DET] pb${tag} run${idx} DONE span=${RUN_SPAN}s rows=${RUN_ROWS} ate_rmse=${ate:-NA} md5=$(md5sum "$OUTDIR/vio.tum"|cut -d' ' -f1)"
}

RATE_TAGS=(1p0 0p5)
GOOD_TAG=""
for tag in "${RATE_TAGS[@]}"; do
  echo "[DET] ===== attempt rate ${tag} (3 isolated full runs) ====="
  all_full=1
  for i in 1 2 3; do
    run_once "$tag" "$i" || { all_full=0; echo "[DET] run failed -> escalate rate"; break; }
    awk_cmp=$(awk -v s="$RUN_SPAN" -v m="$FULL_SPAN_MIN" 'BEGIN{print (s>=m)?1:0}')
    if [[ "$awk_cmp" -ne 1 ]]; then
      echo "[DET] pb${tag} run${i} TRUNCATED (span ${RUN_SPAN}s < ${FULL_SPAN_MIN}s) -> escalate rate"
      all_full=0; break
    fi
  done
  if [[ $all_full -eq 1 ]]; then GOOD_TAG="$tag"; echo "[DET] rate ${tag}: all 3 runs FULL"; break; fi
done

if [[ -z "$GOOD_TAG" ]]; then
  echo "[DET] RESULT: could NOT get 3 full runs even at 0.5 -> truncation persists, report to user."
  echo "[DET] done"; exit 0
fi

echo "[DET] ===== COMPARE 3 full runs at pb${GOOD_TAG} ====="
A="$OUTBASE/pb${GOOD_TAG}_r1/vio.tum"; B="$OUTBASE/pb${GOOD_TAG}_r2/vio.tum"; C="$OUTBASE/pb${GOOD_TAG}_r3/vio.tum"
echo "[DET] md5: r1=$(md5sum "$A"|cut -d' ' -f1) r2=$(md5sum "$B"|cut -d' ' -f1) r3=$(md5sum "$C"|cut -d' ' -f1)"
bid=1; cmp -s "$A" "$B" || bid=0; cmp -s "$A" "$C" || bid=0
[[ $bid -eq 1 ]] && echo "[DET] r1==r2==r3 BIT-IDENTICAL (deterministic)" || echo "[DET] runs NOT bit-identical -> quantify divergence + ATE spread below"
/home/ivlab3/miniconda3/envs/gf/bin/python - "$A" "$B" "$C" "$BASELINE" <<'PY'
import numpy as np, sys
A,B,C,BASE=[np.loadtxt(p) for p in sys.argv[1:5]]
labs=["r1","r2","r3","baseline(dd8d1e0)"]; arrs=[A,B,C,BASE]
def ate_vs_self(x): return None
def pair(x,y):
    n=min(len(x),len(y)); d=np.linalg.norm(x[:n,1:4]-y[:n,1:4],axis=1)
    return np.median(d), d.max(), np.linalg.norm(x[-1,1:4]-y[-1,1:4]) if len(x)==len(y) else float('nan')
for nm,a in zip(labs,arrs): print(f"  {nm}: rows={len(a)} span={a[-1,0]-a[0,0]:.1f}s")
print("  pairwise position |Δ| (median / max meters):")
import itertools
for (i,j) in [(0,1),(0,2),(1,2),(0,3)]:
    md,mx,ep=pair(arrs[i],arrs[j]); print(f"    {labs[i]} vs {labs[j]}: median={md:.2f}m max={mx:.1f}m")
PY
echo "[DET] ate_rmse per run:"
for i in 1 2 3; do printf "  r%d: " $i; grep -iE "^\s*rmse" "$OUTBASE/pb${GOOD_TAG}_r${i}/ape_vio.txt" 2>/dev/null | awk '{print $2}'; done
echo "[DET] done"
