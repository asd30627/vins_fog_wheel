set -eo pipefail
SEQ=urban28-pankyo
WS=/home/ivlab3/fwvio_estimator_ws_wheel
EXT=/mnt/sata4t/datasets/kaist_complex_urban/extracted
SEQROOT="$EXT/$SEQ"; GT="$SEQROOT/pose/$SEQ/global_pose.tum"
TEMPLATE="$WS/src/kaist_player/config/urban28_pankyo_fog.yaml"
SCRATCH="/mnt/sata4t/ivlab3_data/fwvio/results/p1_wheel_v2/_work_wheel/fog/$SEQ"
CTRL="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/bitinv_sited/${SEQ}_ctrl2"
NEW1="/mnt/sata4t/ivlab3_data/fwvio/results/route_c/bitinv_sited/$SEQ/vio_newbin.tum"
mkdir -p "$CTRL"
export REL_PERFEAT_LOG=1 REL_WHEEL_REFERENCE_ONLY=1 PUBLISH_WHEEL_TOPIC=1
export REL_PERFEAT_CSV_PATH="$CTRL/perfeat_throwaway.csv" REL_SEQUENCE_NAME="$SEQ"
unset REL_ANISO_INFO RC_APLUS REL_USE_LEARNED_MODEL REL_ONNX_PATH
bash "$WS/scripts/run_one_p1_baseline.sh" "$SEQ" "$SEQROOT" "$TEMPLATE" "$GT" fog > "$CTRL/runner.log" 2>&1 \
  || { echo "[CTRL] RUNNER FAILED"; tail -20 "$CTRL/runner.log"; exit 1; }
cp -f "$SCRATCH/vins_raw/vio.tum" "$CTRL/vio_new2.tum"; rm -f "$CTRL/perfeat_throwaway.csv"
echo "[CTRL] new1_md5=$(md5sum "$NEW1"|cut -d' ' -f1)  new2_md5=$(md5sum "$CTRL/vio_new2.tum"|cut -d' ' -f1)"
cmp -s "$NEW1" "$CTRL/vio_new2.tum" && echo "[CTRL] new1==new2 BIT-IDENTICAL (deterministic)" || echo "[CTRL] new1!=new2 (nondeterministic same-binary)"
echo "[CTRL] done"
