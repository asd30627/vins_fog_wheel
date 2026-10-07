#!/usr/bin/env bash
# R8-1 scenario-specific preview recorder. Wraps collect_carla_v2.py (host conda `carla` python).
#   usage: r8_record_preview.sh <town> <scenario> <run_tag> <frames>
# scenario in {normal_urban_loop, anchor_recovery, dynamic_noise}
set -o pipefail
TOWN="${1:?town}"; SCEN="${2:?scenario}"; RUNTAG="${3:?run tag}"; FRAMES="${4:-1500}"
CARLA_PY=/home/ivlab3/miniconda3/envs/carla/bin/python
FW=/home/ivlab3/fwvio_ws

COMMON="--imu-at-vehicle-center --baseline 0.5 --drive-mode gentle_loop --speed-mod \
  --base-speed 6.0 --speed-amp 2.0 --speed-period 20.0 --ego-spawn-scan \
  --npc-near-band 8,70 --npc-on-route --npc-skip-ego-lane --npc-autopilot-delay --npc-min-dist 8 \
  --skip-aux --image-width 640 --image-height 480"

case "$SCEN" in
  normal_urban_loop)
    # moderate traffic, ordinary loop, baseline drivability test
    SCEN_ARGS="--npc 12 --npc-global 8"
    ;;
  anchor_recovery)
    # many parked/semi-static objects (candidate anchors) + a few moving/crossing objects
    SCEN_ARGS="--npc 18 --npc-global 8 --npc-static-frac 0.6"
    ;;
  dynamic_noise)
    # lots of moving traffic, few semi-static anchors -> transient culling stress test
    SCEN_ARGS="--npc 22 --npc-global 10 --npc-static-frac 0.1"
    ;;
  *)
    echo "unknown scenario $SCEN"; exit 1 ;;
esac

echo "[r8-record] town=$TOWN scenario=$SCEN frames=$FRAMES args=$SCEN_ARGS"
$CARLA_PY "$FW/scripts/collect_carla_v2.py" \
  --town "$TOWN" --condition dynamic_v3r8 --run "$RUNTAG" \
  --frames "$FRAMES" $COMMON $SCEN_ARGS
