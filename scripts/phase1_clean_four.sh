#!/usr/bin/env bash
# Phase 1: clean-four WHEEL-ON cov-OFF baseline with ADAPTIVE N.
# Same basis as the trio (gate binary 15a57897, wheel topic ON, wheel factor OFF, DL cov OFF,
# callback, fixedext, pb1.0, CARLA off). Per the user's rule:
#   - run each seq N=3 first.
#   - if range% <= 2 (bit-identical / stable) -> STAY N=3.
#   - if range% >  2 (noticeable spread)     -> TOP UP to N=5 (rerun only reps 4,5; median over 1..5).
# RAW table only -- NO win/stability judgment (user judges). Stops on any rep failure.
set -o pipefail
WS=/home/ivlab3/fwvio_estimator_ws_wheel
PY=/home/ivlab3/miniconda3/envs/gf/bin/python
RESROOT=/mnt/sata4t/ivlab3_data/fwvio/results/route_c/phase1_baseline
ate_of(){ grep -iE "^\s*rmse" "$1" 2>/dev/null | awk '{print $2}'; }
range_pct(){ $PY - "$@" <<'PY'
import sys,statistics as st
v=[float(x) for x in sys.argv[1:]]
md=st.median(v); rng=max(v)-min(v)
print(f"{rng/md*100:.4f}")
PY
}

echo "[CLEAN4] ===== clean-four adaptive-N baseline START $(date -Iseconds) ====="
for SEQ in urban28-pankyo urban29-pankyo urban26-dongtan urban27-dongtan; do
  echo "[CLEAN4] ========================= $SEQ : N=3 first ========================="
  bash "$WS/scripts/phase1_baseline.sh" "$SEQ" 3 || { echo "[CLEAN4] $SEQ N=3 FAILED -> STOP"; exit 1; }
  OB="$RESROOT/$SEQ"
  A1=$(ate_of "$OB/rep1/ape_vio.txt"); A2=$(ate_of "$OB/rep2/ape_vio.txt"); A3=$(ate_of "$OB/rep3/ape_vio.txt")
  RP=$(range_pct "$A1" "$A2" "$A3")
  echo "[CLEAN4] $SEQ N=3 ATEs=($A1 $A2 $A3) range=${RP}% of median"
  esc=$($PY -c "print(1 if float('$RP')>2.0 else 0)")
  if [[ "$esc" -eq 1 ]]; then
    echo "[CLEAN4] $SEQ range ${RP}% > 2% -> ESCALATE to N=5 (top up reps 4,5)"
    REP_START=4 bash "$WS/scripts/phase1_baseline.sh" "$SEQ" 5 || { echo "[CLEAN4] $SEQ N=5 escalation FAILED -> STOP"; exit 1; }
    echo "[CLEAN4] $SEQ -> FINAL N=5"
  else
    echo "[CLEAN4] $SEQ range ${RP}% <= 2% -> STAY N=3 (deterministic/stable)"
  fi
done
echo "[CLEAN4] ===== all four done $(date -Iseconds) ====="
