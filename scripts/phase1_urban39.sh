#!/usr/bin/env bash
# Phase 1 trend datapoint baseline: urban39-pankyo wheel-on cov-OFF, ADAPTIVE N.
# Identical basis to the clean four (gate binary 15a57897, wheel topic ON, wheel factor OFF,
# DL cov OFF, callback/no-C2, fixedext, pb1.0, CARLA off, isolated). spec.md L134: urban39 is the
# mid-dynamic TREND datapoint (NOT win, NOT do-no-harm). RAW only, no judgment.
#   - run N=2 first. range<=2% (bit-identical/stable) -> STAY N=2. range>2% -> TOP UP to N=5.
set -o pipefail
WS=/home/ivlab3/fwvio_estimator_ws_wheel
PY=/home/ivlab3/miniconda3/envs/gf/bin/python
SEQ=urban39-pankyo
OB=/mnt/sata4t/ivlab3_data/fwvio/results/route_c/phase1_baseline/$SEQ
ate_of(){ grep -iE "^\s*rmse" "$1" 2>/dev/null | awk '{print $2}'; }
range_pct(){ $PY - "$@" <<'PY'
import sys,statistics as st
v=[float(x) for x in sys.argv[1:]]
md=st.median(v); rng=max(v)-min(v)
print(f"{rng/md*100:.4f}")
PY
}
echo "[U39] ===== urban39 trend-datapoint baseline START $(date -Iseconds) ====="
bash "$WS/scripts/phase1_baseline.sh" "$SEQ" 2 || { echo "[U39] N=2 FAILED -> STOP"; exit 1; }
A1=$(ate_of "$OB/rep1/ape_vio.txt"); A2=$(ate_of "$OB/rep2/ape_vio.txt")
RP=$(range_pct "$A1" "$A2")
echo "[U39] $SEQ N=2 ATEs=($A1 $A2) range=${RP}% of median"
esc=$($PY -c "print(1 if float('$RP')>2.0 else 0)")
if [[ "$esc" -eq 1 ]]; then
  echo "[U39] range ${RP}% > 2% -> ESCALATE to N=5 (top up reps 3,4,5)"
  REP_START=3 bash "$WS/scripts/phase1_baseline.sh" "$SEQ" 5 || { echo "[U39] N=5 escalation FAILED -> STOP"; exit 1; }
  echo "[U39] $SEQ -> FINAL N=5"
else
  echo "[U39] range ${RP}% <= 2% -> STAY N=2 (deterministic/stable)"
fi
echo "[U39] ===== done $(date -Iseconds) ====="
