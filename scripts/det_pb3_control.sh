#!/usr/bin/env bash
# Speed-control experiment: is the cov-OFF nondeterminism caused by playback speed?
# Same new binary (e7e5575), fixedext, cov-OFF, STRICT isolation, but pb 3.0 (vs the pb 1.0 rep1-5).
# 5 runs, each MUST be full (19735 rows / span>=1970 s). If a pb3.0 run TRUNCATES, retry AT pb3.0
# (NOT 0.5 — keep the control pure), up to 3 attempts. Ends with pb3.0 vs pb1.0 side-by-side.
set -o pipefail
SEQ=urban28-pankyo
WS=/home/ivlab3/fwvio_estimator_ws_wheel
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
SEQROOT="$EXT/$SEQ"; GT="$SEQROOT/pose/$SEQ/global_pose.tum"
TEMPLATE="$WS/src/kaist_player/config/urban28_pankyo_fog.yaml"   # ORIGINAL = playback_rate 3.0
SCRATCH="/mnt/sata4t/ivlab3_data/fwvio/results/p1_wheel_v2/_work_wheel/fog/$SEQ"
OUTB="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/det_pb3_control/$SEQ"
mkdir -p "$OUTB"
source /opt/ros/jazzy/setup.bash 2>/dev/null
source "$WS/install/setup.bash" 2>/dev/null
ate_of(){ grep -iE "^\s*rmse" "$1" 2>/dev/null | awk '{print $2}'; }
sr_of(){ awk 'NR==1{f=$1}{l=$1}END{printf "%.1f %d", l-f, NR}' "$1"; }
grep -q "playback_rate: 3.0" "$TEMPLATE" || { echo "[PB3] ABORT: template is not pb3.0"; exit 1; }
echo "[PB3] binary=$(md5sum "$WS/install/vins/lib/vins/vins_node"|cut -d' ' -f1)  pb3.0 fixedext cov-OFF isolated  $(date -Iseconds)"

run_full(){  # $1=idx ; retry at pb3.0 until full, max 3 attempts ; leaves $OUTB/rep$1/{vio.tum,ape_vio.txt}
  local i="$1" attempt=0
  while [ $attempt -lt 3 ]; do
    attempt=$((attempt+1))
    local OUT="$OUTB/rep${i}"; mkdir -p "$OUT"
    export USE_EXPLICIT_FIXEDEXT=1
    export REL_PERFEAT_LOG=1 REL_WHEEL_REFERENCE_ONLY=1 PUBLISH_WHEEL_TOPIC=1
    export REL_PERFEAT_CSV_PATH="$OUT/perfeat_throwaway.csv" REL_SEQUENCE_NAME="$SEQ"
    unset REL_ANISO_INFO RC_APLUS REL_USE_LEARNED_MODEL REL_ONNX_PATH
    echo "[PB3] >>> rep${i} attempt${attempt} (pb3.0) START $(date +%H:%M:%S)"
    bash "$WS/scripts/run_one_p1_baseline.sh" "$SEQ" "$SEQROOT" "$TEMPLATE" "$GT" fog > "$OUT/runner.log" 2>&1
    local rc=$?; rm -f "$OUT/perfeat_throwaway.csv"
    if [[ $rc -ne 0 || ! -s "$SCRATCH/vins_raw/vio.tum" ]]; then echo "[PB3] rep${i} attempt${attempt} RUNNER FAILED rc=$rc"; continue; fi
    cp -f "$SCRATCH/vins_raw/vio.tum" "$OUT/vio.tum"; cp -f "$SCRATCH/metrics/ape_vio.txt" "$OUT/ape_vio.txt" 2>/dev/null || true
    read sp rw < <(sr_of "$OUT/vio.tum")
    local full=$(awk -v s="$sp" 'BEGIN{print (s>=1970.0)?1:0}')
    echo "[PB3] rep${i} attempt${attempt} DONE span=${sp}s rows=${rw} ate=$(ate_of "$OUT/ape_vio.txt") md5=$(md5sum "$OUT/vio.tum"|cut -d' ' -f1) full=${full}"
    [[ "$full" -eq 1 ]] && return 0
    echo "[PB3] rep${i} attempt${attempt} TRUNCATED -> retry at pb3.0"
  done
  echo "[PB3] rep${i} could NOT get a full pb3.0 run in 3 attempts -> ABORT"; return 1
}

for i in 1 2 3 4 5; do run_full "$i" || exit 1; done

echo "[PB3] =========== pb3.0 (5) vs pb1.0 (5) — urban28 cov-OFF fixedext isolated ==========="
P3A=(); P3M=()
for i in 1 2 3 4 5; do P3A+=("$(ate_of "$OUTB/rep${i}/ape_vio.txt")"); P3M+=("$(md5sum "$OUTB/rep${i}/vio.tum"|cut -d' ' -f1)"); done
/home/ivlab3/miniconda3/envs/gf/bin/python - "${P3A[@]}" "${P3M[@]}" <<'PY'
import sys
a=sys.argv[1:6]; m=sys.argv[6:11]
av=[float(x) for x in a]
# pb1.0 reference (rep1-5, measured earlier)
p1a=[16.157526,16.880505,19.048923,18.820856,16.157526]
p1m=["42f345e5","937422bc","9bf8bcd3","07b7217e","42f345e5"]
def stats(v):
    import statistics as st
    return min(v),max(v),st.median(v),st.pstdev(v),(max(v)-min(v)),(max(v)-min(v))/st.median(v)*100
def ndist(ms): return len(set(ms))
print("[PB3]   rep |        pb3.0 ATE  md5(8) |        pb1.0 ATE  md5(8)")
for i in range(5):
    print(f"[PB3]    {i+1}  | {av[i]:14.4f}  {m[i][:8]} | {p1a[i]:14.4f}  {p1m[i]}")
n3,x3,md3,sd3,sp3,spp3=stats(av); n1,x1,md1,sd1,sp1,spp1=stats(p1a)
print(f"[PB3]   ---- pb3.0: min={n3:.3f} max={x3:.3f} median={md3:.3f} std={sd3:.3f} spread={sp3:.3f}m ({spp3:.1f}% of median) distinct_md5={ndist([x[:8] for x in m])}/5")
print(f"[PB3]   ---- pb1.0: min={n1:.3f} max={x1:.3f} median={md1:.3f} std={sd1:.3f} spread={sp1:.3f}m ({spp1:.1f}% of median) distinct_md5={ndist(p1m)}/5(+rep4=baseline)")
allid = len(set([x[:12] for x in m]))==1
print(f"[PB3]   ---- MECHANICAL: pb3.0 5-runs all bit-identical? {'YES (all 5 same md5)' if allid else 'NO ('+str(ndist([x[:8] for x in m]))+' distinct trajectories)'}")
PY
echo "[PB3] done"
