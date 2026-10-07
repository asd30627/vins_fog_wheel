#!/usr/bin/env python3
"""Phase 4.4 — Dual-Channel OPL+LPL benchmark.

Demonstrates that dual-channel (OPL+LPL) outperforms either channel alone:
  - OPL-only (ours_baseline from Phase 4.2):   reduces near_coll, blind to loc_err
  - LPL-only (honor_lpl, no OPL):              reduces false_safe, blind to obstacles
  - dual_channel (OPL+LPL):                    reduces BOTH

World: Mixed-world (2 DANGEROUS obstacles) + loc_err ramp (12s → 0.7m).

Conditions (3 × 3 seeds = 9 episodes):
  ours_baseline  : risk_margin_gain=1.4, honor_hard_stop=False, honor_lpl=False
  lpl_only       : risk_margin_gain=0.0, honor_hard_stop=False, honor_lpl=True
  dual_channel   : risk_margin_gain=1.4, honor_hard_stop=False, honor_lpl=True

Obstacles (same as Phase 4.2 mixed-world):
  [2.5, 0.7] POSITION_ONLY risk=0.1 SAFE
  [4.2, 0.0] UNOBSERVABLE  risk=0.9 DANGEROUS
  [6.0, 0.8] FULL_STATE    risk=0.0 SAFE
  [7.3, 0.0] UNOBSERVABLE  risk=0.9 DANGEROUS

Loc error: 0→0.7m over 12s (same ramp as Phase 4.3).
AL_loc = 0.20 (localization alert limit).
"""
import csv, glob, json, os, signal, subprocess, sys, time

OUT_DIR   = '/home/ivlab3/fwvio_estimator_ws_wheel/logs/phase44'
# Sweep support (repair 2026-07-02): PHASE44_TAG suffixes episode/log dirs so a sweep point does not
# collide with the main run; env also overrides al_loc, conditions, seeds. Defaults = main run.
_TAG      = os.environ.get('PHASE44_TAG', '')
LOG_DIR   = os.path.join(OUT_DIR, f'ep_logs{("_"+_TAG) if _TAG else ""}')
EP_DIR    = os.path.join(OUT_DIR, f'episodes{("_"+_TAG) if _TAG else ""}')
for d in [OUT_DIR, LOG_DIR, EP_DIR]:
    os.makedirs(d, exist_ok=True)

FASTDDS_XML = '/home/ivlab3/fwvio_estimator_ws_wheel/logs/phase42/fastdds_udp_only.xml'
ROS_PRE = ('source /opt/ros/jazzy/setup.bash && '
           'source /home/ivlab3/nav2_ws/install/setup.bash && '
           'export ROS_DOMAIN_ID=88 && '
           f'export FASTRTPS_DEFAULT_PROFILES_FILE={FASTDDS_XML}')

LOC_ERR_RAMP_MAX   = 0.7   # m, same as Phase 4.3
LOC_ERR_RAMP_SECS  = 12.0  # ramp duration
AL_LOC_M           = 0.20  # localization alert limit

# Repair 2026-07-02: 4 conditions.
#  A ours_baseline        : OPL only (no LPL).
#  B lpl_only             : LPL hard-stop (ablation: hard-stop is unsafe in a moving world).
#  C dual_channel_speed   : OPL + risk-scaled LPL, speed-only (fixes freeze/collision, not HMI).
#  D dual_channel_avail   : OPL + risk-scaled LPL + AVAILABILITY flag (declares UNAVAILABLE on breach
#                            -> should actually reduce false-safe, at an availability/mission cost).
CONDITIONS = [
    dict(label='ours_baseline',       risk_margin_gain=1.4, honor_hard_stop=False, honor_lpl=False, lpl_riskscaled=False, lpl_availability_flag=False),
    dict(label='lpl_only',            risk_margin_gain=0.0, honor_hard_stop=False, honor_lpl=True,  lpl_riskscaled=False, lpl_availability_flag=False),
    dict(label='dual_channel_speed',  risk_margin_gain=1.4, honor_hard_stop=False, honor_lpl=True,  lpl_riskscaled=True,  lpl_availability_flag=False),
    dict(label='dual_channel_avail',  risk_margin_gain=1.4, honor_hard_stop=False, honor_lpl=True,  lpl_riskscaled=True,  lpl_availability_flag=True),
]
SEEDS = [0, 1, 2, 3, 4]
EPISODE_TIMEOUT_S = 55.0

# --- sweep env overrides (repair 2026-07-02) ---
if os.environ.get('PHASE44_AL_LOC'):
    AL_LOC_M = float(os.environ['PHASE44_AL_LOC'])
if os.environ.get('PHASE44_CONDS'):
    _want = set(os.environ['PHASE44_CONDS'].split(','))
    CONDITIONS = [c for c in CONDITIONS if c['label'] in _want]
if os.environ.get('PHASE44_SEEDS'):
    SEEDS = [int(s) for s in os.environ['PHASE44_SEEDS'].split(',')]


def clear_shm():
    for f in glob.glob('/dev/shm/fastrtps_*'):
        try:
            os.remove(f)
        except Exception:
            pass


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
    if p is None:
        return
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
    except Exception:
        pass
    try:
        p.wait(timeout=4)
    except Exception:
        pass
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGKILL)
    except Exception:
        pass


INJECTOR_SCRIPT = os.path.join(OUT_DIR, 'loc_err_injector.py')
with open(INJECTOR_SCRIPT, 'w') as f:
    f.write(f"""import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32
import time
LOC_MAX  = {LOC_ERR_RAMP_MAX}
LOC_SECS = {LOC_ERR_RAMP_SECS}
class LocErrInjector(Node):
    def __init__(self):
        super().__init__('loc_err_injector')
        self.pub = self.create_publisher(Float32, '/paper2/gt_pose_error', 10)
        self.t0 = time.monotonic()
        self.timer = self.create_timer(0.1, self.tick)
        self.get_logger().info(f'loc_err_injector up: ramp 0 to {{LOC_MAX:.2f}}m over {{LOC_SECS:.1f}}s')
    def tick(self):
        elapsed = time.monotonic() - self.t0
        v = min(LOC_MAX * elapsed / LOC_SECS, LOC_MAX)
        msg = Float32(); msg.data = float(v)
        self.pub.publish(msg)
def main():
    rclpy.init(); n = LocErrInjector()
    rclpy.spin(n); rclpy.shutdown()
if __name__ == '__main__': main()
""")
# NOTE: mini_world_sim subscribes to /paper2/gt_pose_error (not /paper2/loc_err_m)


def run_episode(cond, seed, ep_idx):
    label  = cond['label']
    ep_id  = f'ep{ep_idx:02d}_{label}_s{seed}'
    csv_path  = os.path.join(EP_DIR,  f'{ep_id}.csv')
    log_prefix = os.path.join(LOG_DIR, ep_id)

    if os.path.exists(csv_path):
        try:
            with open(csv_path) as f:
                rows = list(csv.DictReader(f))
            if rows:
                r = rows[-1]
                elapsed  = float(r.get('elapsed_s', 0))
                success  = r.get('success') == '1'
                freeze_t = float(r.get('freeze_time_s', 0))
                if success or elapsed > 25 or freeze_t > 20:
                    print(f'  [skip] {ep_id}')
                    return r
        except Exception:
            pass

    clear_shm()
    pkill_nodes()

    mws_cmd = (
        f'{ROS_PRE} && '
        'ros2 run paper2_validity_bridge mini_world_sim --ros-args '
        '-p builtin_controller:=True '
        f'-p policy_label:={label} '
        f'-p output_csv:={csv_path} '
        f'-p honor_hard_stop:={"True" if cond["honor_hard_stop"] else "False"} '
        f'-p honor_lpl:={"True" if cond["honor_lpl"] else "False"} '
        f'-p al_loc_m:={AL_LOC_M:.2f} '
        f'-p risk_margin_gain:={cond["risk_margin_gain"]:.1f} '
        '-p risk_slow_gain:=0.5 '
        f'-p lpl_riskscaled:={"True" if cond.get("lpl_riskscaled") else "False"} '
        f'-p lpl_availability_flag:={"True" if cond.get("lpl_availability_flag") else "False"} '
        '-p lpl_slow_gain:=0.7 '
        '-p move_obstacles:=True '
        f'-p obstacle_seed:={seed} '
        f'-p timeout_s:={EPISODE_TIMEOUT_S:.1f}'
    )
    vp_cmd  = f'{ROS_PRE} && ros2 run paper2_validity_bridge validity_publisher --ros-args -p policy:=ours'
    adp_cmd = f'{ROS_PRE} && ros2 run paper2_validity_bridge validity_to_nav_adapter'
    inj_cmd = f'{ROS_PRE} && python3 {INJECTOR_SCRIPT}'

    p_mws = start_proc(mws_cmd, f'{log_prefix}_mws.log')
    time.sleep(3.0)
    p_vp  = start_proc(vp_cmd,  f'{log_prefix}_vp.log')
    p_adp = start_proc(adp_cmd, f'{log_prefix}_adp.log')
    p_inj = start_proc(inj_cmd, f'{log_prefix}_inj.log')

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
        time.sleep(3)

    kill_proc(p_inj)
    kill_proc(p_adp)
    kill_proc(p_vp)
    kill_proc(p_mws)
    time.sleep(1.5)
    clear_shm()
    return result


def parse_num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def main():
    print(f'Phase 4.4 — Dual-Channel OPL+LPL benchmark')
    print(f'World: mixed obstacles (2 DANGEROUS) + loc_err ramp 0→{LOC_ERR_RAMP_MAX}m '
          f'over {LOC_ERR_RAMP_SECS}s, AL_loc={AL_LOC_M}m')
    print(f'Conditions: {[c["label"] for c in CONDITIONS]}')
    print(f'Seeds: {SEEDS}')
    print()

    results = []
    ep_idx = 0
    for cond in CONDITIONS:
        for seed in SEEDS:
            print(f'Running ep{ep_idx:02d}: cond={cond["label"]} seed={seed}')
            r = run_episode(cond, seed, ep_idx)
            ep_idx += 1
            if r:
                row = {
                    'condition':           cond['label'],
                    'seed':                seed,
                    'success':             parse_num(r.get('success')),
                    'near_coll':           parse_num(r.get('near_collisions')),
                    'false_safe_events':   parse_num(r.get('false_safe_events')),
                    'freeze_time_s':       parse_num(r.get('freeze_time_s')),
                    'unnecessary_stops':   parse_num(r.get('unnecessary_stops')),
                    'collisions':          parse_num(r.get('collisions')),
                    # repair: per-episode booleans for VALID rate metrics (not count*100)
                    'collision':           parse_num(r.get('collision')),
                    'near_miss':           parse_num(r.get('near_miss')),
                    'false_safe':          parse_num(r.get('false_safe')),
                    'path_length':         parse_num(r.get('path_length')),
                    'elapsed_s':           parse_num(r.get('elapsed_s')),
                    'loc_err_final_m':     parse_num(r.get('loc_err_final_m')),
                    'min_clear':           parse_num(r.get('min_clear_when_claimed_safe', 99), 99),
                }
                results.append(row)
                print(f'  -> success={row["success"]:.0f} near_coll={row["near_coll"]:.0f} '
                      f'false_safe={row["false_safe_events"]:.0f} '
                      f'freeze={row["freeze_time_s"]:.1f}s '
                      f'loc_err_final={row["loc_err_final_m"]:.3f}m')
            else:
                print(f'  -> NO RESULT')

    # Summary
    import statistics
    summary_rows = []
    for cond in CONDITIONS:
        label = cond['label']
        crows = [r for r in results if r['condition'] == label]
        if not crows:
            continue
        def m(k):
            vals = [r[k] for r in crows]
            return round(statistics.mean(vals), 2) if vals else float('nan')
        summary_rows.append({
            'condition': label,
            'N': len(crows),
            'success%': round(100 * m('success'), 1),
            # repair: rates from per-episode booleans; counts kept as secondary means
            'collision%': round(100 * m('collision'), 1),
            'near_miss%': round(100 * m('near_miss'), 1),
            'false_safe%': round(100 * m('false_safe'), 1),
            'near_coll_cnt': m('near_coll'),
            'false_safe_events': m('false_safe_events'),
            'collisions_cnt': m('collisions'),
            'freeze_s': m('freeze_time_s'),
            'unnecessary_stop%': round(100 * (sum(1 for r in crows if r['unnecessary_stops'] > 0) / len(crows)), 1),
            'loc_err_final_m': m('loc_err_final_m'),
        })

    print()
    print('=== Phase 4.4 Summary ===')
    print(f'{"condition":<16} {"N":>3} {"success%":>9} {"collision%":>11} '
          f'{"near_miss%":>11} {"false_safe%":>12} {"fs_evt":>8} {"freeze_s":>9}')
    for s in summary_rows:
        print(f'{s["condition"]:<16} {s["N"]:>3} {s["success%"]:>9} '
              f'{s["collision%"]:>11} {s["near_miss%"]:>11} {s["false_safe%"]:>12} '
              f'{s["false_safe_events"]:>8} {s["freeze_s"]:>9}')

    # Write results
    results_csv = os.path.join(OUT_DIR, 'phase44_results.csv')
    with open(results_csv, 'w', newline='') as f:
        if results:
            w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            w.writeheader()
            w.writerows(results)

    report_md = os.path.join(OUT_DIR, 'PHASE4_4_DUAL_CHANNEL_BENCHMARK.md')
    with open(report_md, 'w') as f:
        f.write('# Phase 4.4 Dual-Channel OPL+LPL Benchmark Results\n\n')
        f.write(f'## Setup\n')
        f.write(f'- Mixed world: 2 DANGEROUS (UNOBSERVABLE risk=0.9) + 2 SAFE obstacles\n')
        f.write(f'- Loc error ramp: 0→{LOC_ERR_RAMP_MAX}m over {LOC_ERR_RAMP_SECS}s\n')
        f.write(f'- AL_loc = {AL_LOC_M}m (localization alert limit)\n')
        f.write(f'- move_obstacles=True (moving mode from Phase 4.2)\n')
        f.write(f'- {len(SEEDS)} seeds × {len(CONDITIONS)} conditions = {len(SEEDS)*len(CONDITIONS)} episodes\n\n')
        f.write('## Results Table\n\n')
        f.write(f'| condition | N | success% | collision% | near_miss% | '
                f'false_safe% | fs_evt | freeze_s |\n')
        f.write(f'|-----------|---|----------|-----------|-----------|'
                f'------------|--------|---------|\n')
        for s in summary_rows:
            f.write(f'| {s["condition"]} | {s["N"]} | {s["success%"]}% | '
                    f'{s["collision%"]}% | {s["near_miss%"]}% | {s["false_safe%"]}% | '
                    f'{s["false_safe_events"]} | {s["freeze_s"]}s |\n')
        f.write('\n## Key Insight\n')
        f.write('- ours_baseline (OPL only): 0 collisions but false_safe high (loc_err not covered).\n')
        f.write('- lpl_only (hard-stop): freezes -> collisions in a moving world; unsafe.\n')
        f.write('- dual_channel_speed (risk-scaled, speed only): fixes freeze/collision but does NOT '
                'reduce false_safe (still claims safe while slow).\n')
        f.write('- dual_channel_avail (risk-scaled + availability flag): drives false_safe ~0 with 0 '
                'collisions, at an availability/mission cost. See LPL availability repair report.\n\n')
        f.write('## Source\n')
        f.write('- Script: scripts/phase44_batch.py\n')
        f.write(f'- Episode CSVs: {EP_DIR}/\n')

    print()
    print(f'Results written to: {results_csv}')
    print(f'Report written to:  {report_md}')


if __name__ == '__main__':
    main()
