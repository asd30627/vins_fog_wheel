#!/usr/bin/env bash
# Step 3 V1 (value-layer ONLY): prove the player's wheel DUMP == the /wheel/delta it actually publishes,
# bit-identical. Run the (rebuilt) player on urban28 with dump_wheel_path set, side-record the wire with a
# reliable rclpy subscriber, then compare. NOTE: this only verifies the value layer; the preint-layer
# (w_dx/dy/dtheta train/deploy consistency) is Step 5 / V2, NOT here.
set -o pipefail
WS=/home/ivlab3/fwvio_estimator_ws_wheel
OUT=/mnt/sata4t/ivlab3_data/fwvio/results/route_c/v1_wheel_value/urban28-pankyo
SRC_CFG=/mnt/sata4t/ivlab3_data/fwvio/results/p1_wheel_v2/_work_wheel/fog/urban28-pankyo/logs/kaist_player_config.yaml
DUMP="$OUT/wheel_dump.csv"
RECV="$OUT/wheel_published.csv"
CFG="$OUT/player_v1.yaml"
PLAYER_BIN="$WS/install/kaist_player/lib/kaist_player/kaist_player_node"
mkdir -p "$OUT"
source /opt/ros/jazzy/setup.bash 2>/dev/null
source "$WS/install/setup.bash" 2>/dev/null
rm -f "$DUMP" "$RECV"

# config copy + inject dump_wheel_path (publish_wheel_topic already true, playback_rate 3.0, start_offset 0)
/home/ivlab3/miniconda3/envs/gf/bin/python - "$SRC_CFG" "$CFG" "$DUMP" <<'PY'
import sys, re
src, dst, dump = sys.argv[1:4]
t = open(src).read()
if 'dump_wheel_path' not in t:
    t = re.sub(r'(^(\s*)publish_wheel_topic:.*$)', r'\1\n\2dump_wheel_path: "%s"' % dump, t, count=1, flags=re.M)
else:
    t = re.sub(r'^(\s*)dump_wheel_path:.*$', r'\1dump_wheel_path: "%s"' % dump, t, count=1, flags=re.M)
open(dst,'w').write(t)
print("[V1] wrote config", dst, " dump_wheel_path=", dump)
PY
grep -nE "publish_wheel_topic|dump_wheel_path|playback_rate" "$CFG"

echo "[V1] launch recorder (reliable) + player ($(date +%H:%M:%S))"
python3 "$WS/scripts/v1_wheel_recorder.py" "$RECV" > "$OUT/recorder.log" 2>&1 &
REC_PID=$!
sleep 3   # let the subscriber come up before the player starts publishing
"$PLAYER_BIN" --ros-args --params-file "$CFG" > "$OUT/player.log" 2>&1 &
PLAY_PID=$!

# wait for the player to finish publishing all events
echo "[V1] waiting for 'Playback finished.' ..."
for i in $(seq 1 1200); do
  grep -q "Playback finished." "$OUT/player.log" 2>/dev/null && break
  kill -0 "$PLAY_PID" 2>/dev/null || { echo "[V1] player exited early"; break; }
  sleep 2
done
sleep 5   # drain in-flight messages to the recorder
kill -INT "$REC_PID" 2>/dev/null; sleep 2
kill -9 "$PLAY_PID" "$REC_PID" 2>/dev/null
wait 2>/dev/null

echo "[V1] dump log line:"; grep -E "C2 wheel dump" "$OUT/player.log" || echo "  (no dump log!)"
echo "[V1] recorder log line:"; grep -E "V1 recorder" "$OUT/recorder.log" || echo "  (no recorder log!)"

echo "[V1] ==== bit-identical compare: every published /wheel/delta vs dump ===="
/home/ivlab3/miniconda3/envs/gf/bin/python - "$DUMP" "$RECV" <<'PY'
import sys
dump_path, recv_path = sys.argv[1:3]
dump = {}
for ln in open(dump_path):
    if not ln.strip() or ln[0]=='#': continue
    ts, dl, dr, df = ln.strip().split(',')
    dump[int(ts)] = (float(dl), float(dr), float(df))
recv = []
for ln in open(recv_path):
    if not ln.strip(): continue
    ts, x, y, z = ln.strip().split(',')
    recv.append((int(ts), float(x), float(y), float(z)))
print(f"[V1] dump samples N = {len(dump)}")
print(f"[V1] published (recorded) M = {len(recv)}")
missing = 0; mismatch = 0; matched = 0
for ts, x, y, z in recv:
    if ts not in dump: missing += 1; continue
    dl, dr, df = dump[ts]
    if (x==dl) and (y==dr) and (z==df): matched += 1
    else:
        mismatch += 1
        if mismatch <= 5: print(f"  MISMATCH ts={ts} pub=({x!r},{y!r},{z!r}) dump=({dl!r},{dr!r},{df!r})")
print(f"[V1] matched(bit-identical)={matched}  mismatch={mismatch}  published-not-in-dump={missing}")
ok = (len(recv)>0 and len(dump)>0 and mismatch==0 and missing==0 and len(recv)==len(dump))
print(f"[V1] RESULT: {'PASS — value layer bit-identical (dump==published)' if ok else 'CHECK — see counts/mismatch above'}")
PY
echo "[V1] done"
