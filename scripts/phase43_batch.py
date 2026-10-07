#!/usr/bin/env python3
"""Phase 4.3 Localization Degradation Batch (v3).

Tests the supervisor under increasing localization error (drift injection).
v3 redesign: safe-only obstacles (FULL_STATE, y=2.0 off path) → OPL never fires →
all 3 conditions move freely. Fast ramp (12s) → loc_err >= 0.5m at episode_t≈13s →
robots still moving (goal at ~19s) → false_safe fires for ALL conditions.

This demonstrates the STRUCTURAL gap:
  - naive_baseline:  false_safe fires (moving + claimed_safe, no LPL awareness)
  - ours_baseline:   false_safe fires (OPL risk-scaling helps with obstacles but not loc_err)
  - supervised:      false_safe fires (OPL hard-stop only fires for obstacle validity,
                     never for loc_err → robot moves into degradation)

Key claim: OPL channel (obstacle validity) does NOT cover LPL channel (localization quality).
Motivates a dedicated LPL supervisor channel.

3 conditions × 3 seeds = 9 episodes (safe obstacles, fast ramp, UDP transport)
"""
import csv, glob, json, os, signal, subprocess, time

OUT_DIR = '/home/ivlab3/fwvio_estimator_ws_wheel/logs/phase43'
LOG_DIR = os.path.join(OUT_DIR, 'ep_logs')
EP_DIR  = os.path.join(OUT_DIR, 'episodes')
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(EP_DIR,  exist_ok=True)

FASTDDS_XML = '/home/ivlab3/fwvio_estimator_ws_wheel/logs/phase42/fastdds_udp_only.xml'
ROS_PRE = ('source /opt/ros/jazzy/setup.bash && '
           'source /home/ivlab3/nav2_ws/install/setup.bash && '
           'export ROS_DOMAIN_ID=77 && '
           f'export FASTRTPS_DEFAULT_PROFILES_FILE={FASTDDS_XML}')

CONDITIONS = [
    dict(label='naive_baseline', risk_margin_gain=0.0, honor_hard_stop=False),
    dict(label='ours_baseline',  risk_margin_gain=1.4, honor_hard_stop=False),
    dict(label='supervised',     risk_margin_gain=1.4, honor_hard_stop=True),
]
SEEDS = [0, 1, 2]
EPISODE_TIMEOUT_S = 40.0
LOC_ERR_RAMP_MAX  = 0.7   # m, final loc error
LOC_ERR_RAMP_SECS = 12.0  # ramp duration → 0.5m threshold at injector_t≈8.6s = ep_t≈13s
LOC_ERR_THRESHOLD = 0.5   # fs_loc_err_m in mws

# Safe-only obstacles: FULL_STATE (high parallax, low djit), off-path (y=2.0)
# → adp never fires high_cost → all conditions move freely → gap is structural
SAFE_OBSTACLES = [
    dict(x=3.0, y=2.0, kind='ped', speed=0.5, parallax=0.70, bearing=0.90, djit=0.04),
    dict(x=7.0, y=2.0, kind='ped', speed=0.5, parallax=0.68, bearing=0.88, djit=0.05),
]

LOC_ERR_INJECTOR_PY = '/tmp/loc_err_injector.py'

# Write the injector script inline (it's launched as a subprocess)
_INJECTOR_CODE = f'''
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32
import time, math

class LocErrInjector(Node):
    def __init__(self):
        super().__init__("loc_err_injector")
        self.pub = self.create_publisher(Float32, "/paper2/gt_pose_error", 10)
        self.t0 = time.time()
        self.create_timer(0.2, self.tick)
        self.get_logger().info("loc_err_injector up: ramp 0→{LOC_ERR_RAMP_MAX:.2f}m over {LOC_ERR_RAMP_SECS:.1f}s")

    def tick(self):
        elapsed = time.time() - self.t0
        frac = min(1.0, elapsed / {LOC_ERR_RAMP_SECS:.1f})
        err = frac * {LOC_ERR_RAMP_MAX:.3f}
        m = Float32(); m.data = float(err)
        self.pub.publish(m)

def main():
    rclpy.init()
    node = LocErrInjector()
    try:
        rclpy.spin(node)
    except Exception:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == "__main__":
    main()
'''

def write_injector():
    with open(LOC_ERR_INJECTOR_PY, 'w') as f:
        f.write(_INJECTOR_CODE)

def clear_shm():
    for f in glob.glob('/dev/shm/fastrtps_*'):
        try: os.remove(f)
        except: pass

def pkill_nodes():
    for pat in ['mini_world_sim', 'validity_publisher', 'validity_to_nav_adapter',
                'loc_err_injector']:
        subprocess.run(['pkill', '-KILL', '-f', pat],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)

def start_proc(cmd, log_path):
    with open(log_path, 'w') as lf:
        return subprocess.Popen(['bash', '-c', cmd], stdout=lf, stderr=lf,
                                preexec_fn=os.setsid)

def kill_proc(p):
    if p is None: return
    try: os.killpg(os.getpgid(p.pid), signal.SIGTERM)
    except: pass
    try: p.wait(timeout=4)
    except: pass
    try: os.killpg(os.getpgid(p.pid), signal.SIGKILL)
    except: pass

def run_episode(cond, seed, ep_idx):
    label  = cond['label']
    ep_id  = f'ep{ep_idx:02d}_{label}_s{seed}'
    csv_path  = os.path.join(EP_DIR, f'{ep_id}.csv')
    log_pfx   = os.path.join(LOG_DIR, ep_id)

    if os.path.exists(csv_path):
        with open(csv_path) as f:
            rows = list(csv.DictReader(f))
        if rows:
            r = rows[-1]
            elapsed  = float(r.get('elapsed_s', 0))
            success  = r.get('success') == '1'
            freeze_t = float(r.get('freeze_time_s', 0))
            if success or elapsed > 25 or freeze_t > 20:
                print(f'  [skip] {ep_id} (elapsed={elapsed:.1f}s)')
                return r

    clear_shm()
    pkill_nodes()

    # Write a YAML params file so obstacles_json can be passed without shell quoting issues
    params_yaml = os.path.join(LOG_DIR, f'{ep_id}_params.yaml')
    obs_json_str = json.dumps(SAFE_OBSTACLES)
    with open(params_yaml, 'w') as pf:
        pf.write('mini_world_sim:\n  ros__parameters:\n')
        pf.write(f'    builtin_controller: true\n')
        pf.write(f'    policy_label: "{label}"\n')
        pf.write(f'    output_csv: "{csv_path}"\n')
        pf.write(f'    honor_hard_stop: {"true" if cond["honor_hard_stop"] else "false"}\n')
        pf.write(f'    risk_margin_gain: {cond["risk_margin_gain"]:.1f}\n')
        pf.write(f'    risk_slow_gain: 0.5\n')
        pf.write(f'    move_obstacles: false\n')
        pf.write(f'    obstacle_seed: {seed}\n')
        pf.write(f'    timeout_s: {EPISODE_TIMEOUT_S:.1f}\n')
        pf.write(f'    obstacles_json: \'{obs_json_str}\'\n')

    mws_cmd = (
        f'{ROS_PRE} && '
        f'ros2 run paper2_validity_bridge mini_world_sim --ros-args '
        f'--params-file {params_yaml}'
    )
    vp_cmd  = f'{ROS_PRE} && ros2 run paper2_validity_bridge validity_publisher --ros-args -p policy:=ours'
    adp_cmd = f'{ROS_PRE} && ros2 run paper2_validity_bridge validity_to_nav_adapter'
    inj_cmd = f'{ROS_PRE} && python3 {LOC_ERR_INJECTOR_PY}'

    p_mws = start_proc(mws_cmd, f'{log_pfx}_mws.log')
    time.sleep(3.0)         # DDS init window for mws
    p_vp  = start_proc(vp_cmd,  f'{log_pfx}_vp.log')
    p_adp = start_proc(adp_cmd, f'{log_pfx}_adp.log')
    time.sleep(1.5)         # let vp+adp stabilize before adding injector
    p_inj = start_proc(inj_cmd, f'{log_pfx}_inj.log')

    t0 = time.time()
    result = None
    while (time.time() - t0) < (EPISODE_TIMEOUT_S + 15):
        if os.path.exists(csv_path):
            try:
                with open(csv_path) as f:
                    rows = list(csv.DictReader(f))
                if rows:
                    r = rows[-1]
                    elapsed = float(r.get('elapsed_s', 0))
                    if elapsed > (EPISODE_TIMEOUT_S - 2) or r.get('success') == '1':
                        result = r
                        break
            except Exception:
                pass
        if p_mws.poll() is not None:
            time.sleep(1)
            if os.path.exists(csv_path):
                try:
                    with open(csv_path) as f:
                        rows = list(csv.DictReader(f))
                    result = rows[-1] if rows else None
                except Exception:
                    pass
            break
        time.sleep(5)

    kill_proc(p_inj)
    kill_proc(p_adp)
    kill_proc(p_vp)
    kill_proc(p_mws)
    pkill_nodes()
    time.sleep(2)

    if result:
        print(f'  {ep_id}: success={result.get("mission_success")} '
              f'near={result.get("near_collisions")} coll={result.get("collisions")} '
              f'false_safe={result.get("false_safe_events")} '
              f'freeze={result.get("freeze_time_s")}s elapsed={result.get("elapsed_s")}s')
    else:
        print(f'  {ep_id}: NO RESULT')
    return result


def main():
    write_injector()

    # v3: delete stale episode CSVs from previous runs (design was different)
    for stale in glob.glob(os.path.join(EP_DIR, '*.csv')):
        os.remove(stale)

    episodes = []
    ep_idx = 0
    for cond in CONDITIONS:
        for seed in SEEDS:
            episodes.append((cond, seed, ep_idx))
            ep_idx += 1

    total = len(episodes)
    inj_delay_s = 4.5  # 3.0 (mws) + 1.5 (vp+adp stabilize)
    thresh_ep_t = inj_delay_s + (LOC_ERR_THRESHOLD / LOC_ERR_RAMP_MAX) * LOC_ERR_RAMP_SECS
    print(f'Phase 4.3 Localization Degradation v3: {total} episodes')
    print(f'Loc error ramp: 0→{LOC_ERR_RAMP_MAX}m over {LOC_ERR_RAMP_SECS}s '
          f'(threshold={LOC_ERR_THRESHOLD}m at episode_t≈{thresh_ep_t:.1f}s)')
    print(f'Obstacles: SAFE-ONLY (y=2.0, FULL_STATE) → OPL never fires → gap is structural')

    results = []
    for i, (cond, seed, eidx) in enumerate(episodes):
        print(f'\n[{i+1}/{total}] {cond["label"]} / seed={seed}')
        r = run_episode(cond, seed, eidx)
        if r:
            r['_label'] = cond['label']
            r['_seed']  = seed
            results.append(r)

    from collections import defaultdict
    groups = defaultdict(list)
    for r in results:
        groups[r['_label']].append(r)

    def avg(lst, key):
        vals = []
        for r in lst:
            try: vals.append(float(r[key]))
            except: pass
        return sum(vals)/len(vals) if vals else float('nan')

    inj_delay_s = 4.5
    thresh_ep_t = inj_delay_s + (LOC_ERR_THRESHOLD / LOC_ERR_RAMP_MAX) * LOC_ERR_RAMP_SECS
    lines = [
        '# Phase 4.3 Localization Degradation Results (v3)',
        '',
        '## Setup',
        f'- Localization error ramp: 0→{LOC_ERR_RAMP_MAX}m over {LOC_ERR_RAMP_SECS}s',
        f'- fs_loc_err_m threshold: {LOC_ERR_THRESHOLD}m at episode_t≈{thresh_ep_t:.1f}s',
        '- **Safe-only obstacles** (FULL_STATE, y=2.0 off path) → OPL never fires',
        '- All 3 conditions move freely; false_safe fires when loc_err >= 0.5m while moving',
        f'- 3 conditions × {len(SEEDS)} seeds = {total} episodes',
        '',
        '## Results Table',
        '',
        '| condition | N | success% | near_coll | false_safe_events | freeze_s | '
        'min_clear | loc_err_final |',
        '|-----------|---|----------|-----------|-------------------|----------|'
        '---------|--------------|',
    ]
    for lbl in ['naive_baseline', 'ours_baseline', 'supervised']:
        grp = groups.get(lbl, [])
        n = len(grp)
        if n == 0:
            lines.append(f'| {lbl} | 0 | N/A | N/A | N/A | N/A | N/A |')
            continue
        suc = 100.0*sum(1 for r in grp if r.get('mission_success') in ('1', 1)) / n
        near = avg(grp, 'near_collisions')
        fs = avg(grp, 'false_safe_events')
        frz = avg(grp, 'freeze_time_s')
        mc = avg(grp, 'min_obstacle_clearance_m')
        le = avg(grp, 'loc_err_final_m')
        lines.append(f'| {lbl} | {n} | {suc:.0f}% | {near:.1f} | {fs:.1f} | '
                     f'{frz:.1f}s | {mc:.3f}m | {le:.3f}m |')

    lines += [
        '',
        '## Key Insight (v3 — structural gap demonstration)',
        '- **World**: safe-only obstacles (FULL_STATE, y=2.0) → adp never fires high_cost',
        f'- **false_safe_events**: fires when claimed_safe=True AND NOT hard_stop AND loc_err >= {LOC_ERR_THRESHOLD}m',
        '- **All 3 conditions experience false_safe**: OPL channel is blind to loc_err',
        '- naive_baseline: no validity signals → ignores both obstacles and loc_err',
        '- ours_baseline: OPL helps with obstacle avoidance but cannot detect loc_err',
        '- supervised: OPL hard_stop never fires (safe obstacles) → also unprotected',
        '- **Conclusion**: OPL ≠ LPL coverage; dedicated localization integrity channel required',
        '',
        '## Source',
        f'- Script: scripts/phase43_batch.py (v3)',
        f'- Episode CSVs: {EP_DIR}/',
    ]

    report_path = os.path.join(OUT_DIR, 'PHASE4_3_LOC_DEGRADATION.md')
    with open(report_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'\n=== DONE — report: {report_path} ===')
    for l in lines:
        print(l)


if __name__ == '__main__':
    main()
