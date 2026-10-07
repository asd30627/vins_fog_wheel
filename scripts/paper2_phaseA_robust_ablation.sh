#!/usr/bin/env bash
# Paper-2 Phase A — VINS robust-mechanism ablation (V1/V2/V3/V3b) on the 2 clean+stable runs.
# V1 stock (Huber on, cull on) | V2 Huber off | V3 cull off | V3b both off.
# Huber-off / cull-off are ABLATION ONLY, not method. Emits one CSV row per (run x variant).
# usage: paper2_phaseA_robust_ablation.sh
set -o pipefail
WS=/home/ivlab3/fwvio_estimator_ws_wheel
FW=/home/ivlab3/fwvio_ws
DS=/mnt/sata4t/datasets/carla_fwvio
OUTROOT=/mnt/sata4t/ivlab3_data/fwvio/results/paper2_vinsaware
CSV="$WS/paper2/track_a/paper2_vins_robust_mechanism_metrics.csv"
# DETERMINISTIC config (multiple_thread=0, max_solver_time=0.5) — REQUIRED: the stock config
# (multiple_thread=1 + max_solver_time=0.08) is nondeterministic (~15% ATE run-to-run), which
# swamps switch effects. All Phase A runs use DET so switch deltas are attributable.
export RC_CONFIG="$WS/src/VINS-Fusion-ROS2-jazzy/config/carla/carla_stereo_imu_640_R3_b05_gm_DET2.yaml"

echo "variant,run,huber,cull,ate_rmse,ate_mean,rpe_trans,early_scale,late_scale,vins_fail,feat_raw,feat_mgr,mean_outlier_ratio,opt_final_cost,runtime_s,diverged" > "$CSV"

run_one () {
  local variant="$1" recname="$2" huber="$3" cull="$4"
  local rec="$DS/$recname"
  local runlabel; runlabel=$(echo "$recname" | sed 's/Town01__dynamic_v3__run//')
  local tag="phaseA_${variant}_${runlabel}"
  local outdir="$OUTROOT/$tag"
  export REL_VISUAL_ROBUST_LOSS="$huber"
  export REL_BACKEND_OUTLIER_CULL="$cull"
  local t0; t0=$(date +%s)
  bash "$WS/scripts/paper2_vins_run_one.sh" "$rec" "$tag" 0.5 > "$outdir.driver.log" 2>&1
  local t1; t1=$(date +%s); local rt=$((t1 - t0))
  unset REL_VISUAL_ROBUST_LOSS REL_BACKEND_OUTLIER_CULL
  # trajectory metrics (JSON)
  local mj; mj=$(python3 "$WS/scripts/paper2_vins_metrics.py" "$rec" "$outdir" "$tag" 2>/dev/null | tail -1)
  # internals from vins.log
  local vlog="$outdir/vins.log"
  local orr fraw fmgr optc
  orr=$(grep -oE "ratio=[0-9.]+" "$vlog" 2>/dev/null | sed 's/ratio=//' | awk '{s+=$1;n++} END{if(n)printf "%.4f",s/n; else print "NA"}')
  fraw=$(grep -oE "raw=[0-9]+" "$vlog" 2>/dev/null | sed 's/raw=//' | awk '{s+=$1;n++} END{if(n)printf "%.1f",s/n; else print "NA"}')
  fmgr=$(grep -oE "mgr=[0-9]+" "$vlog" 2>/dev/null | sed 's/mgr=//' | awk '{s+=$1;n++} END{if(n)printf "%.1f",s/n; else print "NA"}')
  optc=$(grep -oE "\[opt-cost\].*final=[0-9.eE+-]+" "$vlog" 2>/dev/null | grep -oE "final=[0-9.eE+-]+" | sed 's/final=//' | awk '{s+=$1;n++} END{if(n)printf "%.4e",s/n; else print "NA"}')
  # parse JSON fields with python
  python3 - "$variant" "$runlabel" "$huber" "$cull" "$rt" "$orr" "$fraw" "$fmgr" "$optc" "$mj" <<'PY' >> "$CSV"
import sys,json
variant,run,huber,cull,rt,orr,fraw,fmgr,optc,mj=sys.argv[1:11]
try: d=json.loads(mj)
except Exception: d={}
def g(k):
    v=d.get(k); return "" if v is None else v
print(",".join(str(x) for x in [variant,run,("on" if huber!="0" else "off"),("on" if cull!="0" else "off"),
    g("ate_rmse"),g("ate_mean"),g("rpe_trans_med"),g("early_scale"),g("late_scale"),g("vins_failures"),
    fraw,fmgr,orr,optc,rt,("1" if d.get("diverged") else "0")]))
PY
  echo "[phaseA] done $tag ate_rmse=$(echo "$mj" | python3 -c 'import sys,json;print(json.loads(sys.stdin.read() or "{}").get("ate_rmse"))' 2>/dev/null) rt=${rt}s"
}

run_one V1   Town01__dynamic_v3__rundense_b1 1 1   # stock
run_one V1rep Town01__dynamic_v3__rundense_b1 1 1  # determinism repeat (MUST == V1)
for rec in Town01__dynamic_v3__rundense_b1 Town01__dynamic_v3__runmedium_b1; do
  [ "$rec" = "Town01__dynamic_v3__rundense_b1" ] || run_one V1 "$rec" 1 1
  run_one V2   "$rec" 0 1     # Huber off
  run_one V3   "$rec" 1 0     # cull off
  run_one V3b  "$rec" 0 0     # both off (may diverge)
done
echo "[phaseA] ALL DONE -> $CSV"
column -t -s, "$CSV"
