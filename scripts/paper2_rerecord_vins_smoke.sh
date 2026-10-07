#!/usr/bin/env bash
# R5: VINS baseline smoke on re-recorded cores. DET2 config, ideal_imu, repeat x2 for determinism.
# NO TCSV. Args: list of run dir names (Town__dynamic_v3fix__run<name>).
WS=/home/ivlab3/fwvio_estimator_ws_wheel
DS=/mnt/sata4t/datasets/carla_fwvio
R=/mnt/sata4t/ivlab3_data/fwvio/results/paper2_vinsaware
export RC_CONFIG="$WS/src/VINS-Fusion-ROS2-jazzy/config/carla/carla_stereo_imu_640_R3_b05_gm_DET2.yaml"
CSV=$WS/paper2/track_a/paper2_rerecorded_vins_baseline_smoke.csv
echo "run,rep,n_vio,ate_rmse,rpe_trans,early,late,vins_fail,feat_raw,feat_mgr,mean_outlier,det_ok" > "$CSV"
cd "$WS"
for run in "$@"; do
  REC="$DS/$run"; [ -d "$REC" ] || { echo "MISSING $run"; continue; }
  prev=""
  for rep in 1 2; do
    tag="smoke_${run}_r${rep}"
    bash scripts/paper2_vins_run_one.sh "$REC" "$tag" 0.5 >/dev/null 2>&1
    mj=$(python3 scripts/paper2_vins_metrics.py "$REC" "$R/$tag" x 2>/dev/null | tail -1)
    vlog="$R/$tag/vins.log"
    orr=$(grep -oE "ratio=[0-9.]+" "$vlog" 2>/dev/null|sed 's/ratio=//'|awk '{s+=$1;n++}END{if(n)printf"%.3f",s/n;else print"NA"}')
    fr=$(grep -oE "raw=[0-9]+" "$vlog" 2>/dev/null|sed 's/raw=//'|awk '{s+=$1;n++}END{if(n)printf"%.0f",s/n;else print"NA"}')
    fm=$(grep -oE "mgr=[0-9]+" "$vlog" 2>/dev/null|sed 's/mgr=//'|awk '{s+=$1;n++}END{if(n)printf"%.0f",s/n;else print"NA"}')
    det="";
    if [ "$rep" = "2" ]; then diff -q "$R/smoke_${run}_r1/vio.csv" "$R/$tag/vio.csv" >/dev/null 2>&1 && det="IDENTICAL" || det="DIFFER"; fi
    echo "$mj" | python3 -c "import sys,json;d=json.loads(sys.stdin.read() or '{}');print('$run',$rep,d.get('n_vio'),d.get('ate_rmse'),d.get('rpe_trans_med'),d.get('early_scale'),d.get('late_scale'),d.get('vins_failures'),'$fr','$fm','$orr','$det',sep=',')" >> "$CSV"
  done
  echo "[smoke] $run done"
done
echo "=== SMOKE ==="; column -t -s, "$CSV"; echo "VINS_SMOKE_DONE"
