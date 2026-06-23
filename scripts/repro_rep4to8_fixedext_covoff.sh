#!/usr/bin/env bash
# Baseline-shape investigation: urban28 cov-OFF, fixedext, pb 1.0, STRICT isolation, ONE VINS at a time.
# Run rep4..rep8 (5 more); combined with rep1/2/3 = 8 full samples. Each MUST be full (~19735 rows /
# span>=1970 s); if truncated at pb1.0, retry that rep at pb0.5 (locked protocol). Ends with the
# 8-sample ATE distribution analysis (min/max/median/std, shape, first-3 vs all-8 median stability).
set -o pipefail
SEQ=urban28-pankyo
WS=/home/ivlab3/fwvio_estimator_ws_wheel
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
SEQROOT="$EXT/$SEQ"; GT="$SEQROOT/pose/$SEQ/global_pose.tum"
SCRATCH="/mnt/sata4t/ivlab3_data/fwvio/results/p1_wheel_v2/_work_wheel/fog/$SEQ"
VBASE="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/verify_fixedext/$SEQ"
BASELINE="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/pretask1_perfeat/$SEQ/vio.tum"
source /opt/ros/jazzy/setup.bash 2>/dev/null
source "$WS/install/setup.bash" 2>/dev/null
ate_of(){ grep -iE "^\s*rmse" "$1" 2>/dev/null | awk '{print $2}'; }
sr_of(){ awk 'NR==1{f=$1}{l=$1}END{printf "%.1f %d", l-f, NR}' "$1"; }

echo "[REPRO48] binary=$(md5sum "$WS/install/vins/lib/vins/vins_node"|cut -d' ' -f1)  pb1.0 fixedext cov-OFF isolated  $(date -Iseconds)"

run_rep(){  # $1=idx $2=rate-tag(1p0/0p5) -> returns 0 if full
  local i="$1" tag="$2"
  local TEMPLATE="$WS/src/kaist_player/config/urban28_pankyo_fog_pb${tag}.yaml"
  local OUT="$VBASE/rep${i}"; mkdir -p "$OUT"
  export USE_EXPLICIT_FIXEDEXT=1
  export REL_PERFEAT_LOG=1 REL_WHEEL_REFERENCE_ONLY=1 PUBLISH_WHEEL_TOPIC=1
  export REL_PERFEAT_CSV_PATH="$OUT/perfeat_throwaway.csv" REL_SEQUENCE_NAME="$SEQ"
  unset REL_ANISO_INFO RC_APLUS REL_USE_LEARNED_MODEL REL_ONNX_PATH
  echo "[REPRO48] >>> rep${i} (pb${tag}) START $(date +%H:%M:%S)"
  bash "$WS/scripts/run_one_p1_baseline.sh" "$SEQ" "$SEQROOT" "$TEMPLATE" "$GT" fog > "$OUT/runner.log" 2>&1
  local rc=$?; rm -f "$OUT/perfeat_throwaway.csv"
  if [[ $rc -ne 0 || ! -s "$SCRATCH/vins_raw/vio.tum" ]]; then echo "[REPRO48] rep${i} RUNNER FAILED rc=$rc"; tail -15 "$OUT/runner.log"; return 2; fi
  cp -f "$SCRATCH/vins_raw/vio.tum" "$OUT/vio.tum"; cp -f "$SCRATCH/metrics/ape_vio.txt" "$OUT/ape_vio.txt" 2>/dev/null || true
  read sp rw < <(sr_of "$OUT/vio.tum")
  local full=$(awk -v s="$sp" 'BEGIN{print (s>=1970.0)?1:0}')
  echo "[REPRO48] rep${i} (pb${tag}) DONE span=${sp}s rows=${rw} ate=$(ate_of "$OUT/ape_vio.txt") md5=$(md5sum "$OUT/vio.tum"|cut -d' ' -f1) full=${full}"
  [[ "$full" -eq 1 ]] && return 0 || return 1
}

for i in 4 5 6 7 8; do
  if ! run_rep "$i" "1p0"; then
    echo "[REPRO48] rep${i} truncated at pb1.0 -> retry pb0.5 (locked protocol)"
    if ! run_rep "$i" "0p5"; then echo "[REPRO48] rep${i} STILL truncated/failed at pb0.5 -> ABORT, report"; exit 1; fi
  fi
done

echo "[REPRO48] =========== 8-SAMPLE DISTRIBUTION (urban28 cov-OFF fixedext pb1.0 isolated) ==========="
A1=$(ate_of "$VBASE/ape_vio.txt")
A2=$(ate_of "$VBASE/rep2/ape_vio.txt"); A3=$(ate_of "$VBASE/rep3/ape_vio.txt")
A4=$(ate_of "$VBASE/rep4/ape_vio.txt"); A5=$(ate_of "$VBASE/rep5/ape_vio.txt")
A6=$(ate_of "$VBASE/rep6/ape_vio.txt"); A7=$(ate_of "$VBASE/rep7/ape_vio.txt"); A8=$(ate_of "$VBASE/rep8/ape_vio.txt")
for k in 1 2 3 4 5 6 7 8; do v="A$k"; echo "[REPRO48]   rep${k} ATE=${!v}"; done
echo "[REPRO48]   (dd8d1e0 baseline ATE=18.82, a 9th independent sample from the OLD binary)"
/home/ivlab3/miniconda3/envs/gf/bin/python - "$A1" "$A2" "$A3" "$A4" "$A5" "$A6" "$A7" "$A8" <<'PY'
import sys, statistics as st
v=[float(x) for x in sys.argv[1:9]]
s=sorted(v)
md=st.median(v); mn=min(v); mx=max(v); sd=st.pstdev(v); ssd=st.stdev(v)
print(f"[REPRO48-ANALYSIS] n=8  sorted={['%.2f'%x for x in s]}")
print(f"[REPRO48-ANALYSIS] min={mn:.2f} max={mx:.2f} median={md:.3f} mean={st.mean(v):.3f} std(sample)={ssd:.3f} spread={mx-mn:.2f}m ({(mx-mn)/md*100:.1f}% of median)")
m3=st.median(v[:3]); m8=md
print(f"[REPRO48-ANALYSIS] STABILITY: median(first3 rep1-3)={m3:.3f}  median(all8)={m8:.3f}  diff={abs(m3-m8):.3f}m ({abs(m3-m8)/m8*100:.2f}%)")
# shape: how many within +/-0.5 / +/-1.0 of median; IQR-outliers
import statistics
q1=statistics.quantiles(v,n=4)[0]; q3=statistics.quantiles(v,n=4)[2]; iqr=q3-q1
lo=q1-1.5*iqr; hi=q3+1.5*iqr; outl=[x for x in v if x<lo or x>hi]
w05=sum(1 for x in v if abs(x-md)<=0.5); w10=sum(1 for x in v if abs(x-md)<=1.0)
print(f"[REPRO48-ANALYSIS] SHAPE: within +/-0.5m of median={w05}/8, within +/-1.0m={w10}/8; Q1={q1:.2f} Q3={q3:.2f} IQR={iqr:.2f}; IQR-outliers={['%.2f'%x for x in outl] if outl else 'none'}")
PY
echo "[REPRO48] done"
