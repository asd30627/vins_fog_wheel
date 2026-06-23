set -o pipefail
WS=/home/ivlab3/fwvio_estimator_ws_wheel
for SEQ in urban35-seoul urban31-gangnam urban36-seoul; do
  echo "[P1TRIO] ===== $SEQ (N=3) ====="
  bash "$WS/scripts/phase1_baseline.sh" "$SEQ" 3 || { echo "[P1TRIO] $SEQ FAILED -> stop"; exit 1; }
done
echo "[P1TRIO] all trio done"
