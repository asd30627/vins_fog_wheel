#!/usr/bin/env python3
"""Phase 4.2 Mixed-World Benchmark batch runner.

30 episodes: 3 conditions × 2 obstacle modes × 5 seeds.

Conditions
  naive_baseline : risk_margin_gain=0.0,  honor_hard_stop=False
  ours_baseline  : risk_margin_gain=1.4,  honor_hard_stop=False  (margin-scaled only)
  supervised     : risk_margin_gain=1.4,  honor_hard_stop=True   (margin + hard-stop)

Obstacle modes
  static  : move_obstacles=False
  moving  : move_obstacles=True

Mixed world (default obstacles, 4 objects):
  [2.5, 0.7] kind=box speed=0.0  parallax=0.6  → POSITION_ONLY risk=0.1  SAFE
  [4.2, 0.0] kind=deg speed=0.9  parallax=0.12 → UNOBSERVABLE  risk=0.9  DANGEROUS
  [6.0, 0.8] kind=ped speed=1.1  parallax=0.7  → FULL_STATE    risk=0.0  SAFE
  [7.3, 0.0] kind=deg speed=0.8  parallax=0.13 → UNOBSERVABLE  risk=0.9  DANGEROUS
"""
import csv, glob, json, os, signal, subprocess, time

OUT_DIR  = '/home/ivlab3/fwvio_estimator_ws_wheel/logs/phase42'
LOG_DIR  = os.path.join(OUT_DIR, 'ep_logs')
EP_DIR   = os.path.join(OUT_DIR, 'episodes')
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
OBS_MODES = [
    dict(mode_label='static',  move_obstacles=False),
    dict(mode_label='moving',  move_obstacles=True),
]
SEEDS = [0, 1, 2, 3, 4]
EPISODE_TIMEOUT_S = 55.0

def clear_shm():
    for f in glob.glob('/dev/shm/fastrtps_*'):
        try: os.remove(f)
        except: pass

def pkill_nodes():
    for pat in ['mini_world_sim', 'validity_publisher', 'validity_to_nav_adapter']:
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
    try: os.killpg(os.getpgid(p.pid), signal.SIGTERM)
    except: pass
    try: p.wait(timeout=4)
    except: pass
    try: os.killpg(os.getpgid(p.pid), signal.SIGKILL)
    except: pass

def run_episode(cond, obs_mode, seed, ep_idx):
    label      = cond['label']
    mode_label = obs_mode['mode_label']
    ep_id      = f'ep{ep_idx:02d}_{label}_{mode_label}_s{seed}'
    csv_path   = os.path.join(EP_DIR, f'{ep_id}.csv')
    log_prefix = os.path.join(LOG_DIR, ep_id)

    if os.path.exists(csv_path):
        # resume skip: only skip if episode demonstrably ran (success or long episode or freeze)
        with open(csv_path) as f:
            rows = list(csv.DictReader(f))
        if rows:
            r = rows[-1]
            elapsed  = float(r.get('elapsed_s', 0))
            success  = r.get('success') == '1'
            freeze_t = float(r.get('freeze_time_s', 0))
            # Valid if arrived, OR ran long enough, OR meaningful freeze data
            if success or elapsed > 25 or freeze_t > 20:
                print(f'  [skip] {ep_id} (elapsed={elapsed:.1f}s success={r.get("success")} freeze={freeze_t:.1f}s)')
                return r

    # clean state
    clear_shm()
    pkill_nodes()

    mws_cmd = (
        f'{ROS_PRE} && '
        'ros2 run paper2_validity_bridge mini_world_sim --ros-args '
        '-p builtin_controller:=True '
        f'-p policy_label:={label} '
        f'-p output_csv:={csv_path} '
        f'-p honor_hard_stop:={"True" if cond["honor_hard_stop"] else "False"} '
        f'-p risk_margin_gain:={cond["risk_margin_gain"]:.1f} '
        '-p risk_slow_gain:=0.5 '
        f'-p move_obstacles:={"True" if obs_mode["move_obstacles"] else "False"} '
        f'-p obstacle_seed:={seed} '
        f'-p timeout_s:={EPISODE_TIMEOUT_S:.1f}'
    )
    vp_cmd  = f'{ROS_PRE} && ros2 run paper2_validity_bridge validity_publisher --ros-args -p policy:=ours'
    adp_cmd = f'{ROS_PRE} && ros2 run paper2_validity_bridge validity_to_nav_adapter'

    p_mws = start_proc(mws_cmd, f'{log_prefix}_mws.log')
    time.sleep(3.0)                 # DDS shm init window
    p_vp  = start_proc(vp_cmd,  f'{log_prefix}_vp.log')
    p_adp = start_proc(adp_cmd, f'{log_prefix}_adp.log')

    t0 = time.time()
    result = None
    while (time.time() - t0) < (EPISODE_TIMEOUT_S + 12):
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
            # mws exited; read final csv
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

    kill_proc(p_adp)
    kill_proc(p_vp)
    kill_proc(p_mws)
    pkill_nodes()
    time.sleep(2)

    if result:
        elapsed = float(result.get('elapsed_s', 0))
        near  = result.get('near_collisions', '?')
        colls = result.get('collisions', '?')
        frz   = result.get('freeze_time_s', '?')
        unst  = result.get('unnecessary_stop_count', '?')
        miss  = result.get('mission_success', '?')
        print(f'  {ep_id}: success={miss} near={near} coll={colls} '
              f'freeze={frz}s unnec_stop={unst} elapsed={elapsed:.1f}s')
    else:
        print(f'  {ep_id}: NO RESULT')

    return result


def main():
    episodes = []
    ep_idx = 0
    for obs_mode in OBS_MODES:
        for cond in CONDITIONS:
            for seed in SEEDS:
                episodes.append((cond, obs_mode, seed, ep_idx))
                ep_idx += 1

    total = len(episodes)
    print(f'Phase 4.2 Mixed-World Benchmark: {total} episodes')
    print(f'OUT_DIR={OUT_DIR}')

    results = []
    for i, (cond, obs_mode, seed, eidx) in enumerate(episodes):
        print(f'\n[{i+1}/{total}] {cond["label"]} / {obs_mode["mode_label"]} / seed={seed}')
        r = run_episode(cond, obs_mode, seed, eidx)
        if r:
            r['_label'] = cond['label']
            r['_mode']  = obs_mode['mode_label']
            r['_seed']  = seed
            results.append(r)

    # ---------- summary ----------
    from collections import defaultdict
    groups = defaultdict(list)
    for r in results:
        key = (r['_label'], r['_mode'])
        groups[key].append(r)

    def avg(lst, key):
        vals = []
        for r in lst:
            try: vals.append(float(r[key]))
            except: pass
        return sum(vals) / len(vals) if vals else float('nan')

    def pct(lst, key, val=1):
        if not lst: return float('nan')
        return 100.0 * sum(1 for r in lst if str(r.get(key, '')) == str(val)) / len(lst)

    lines = ['# Phase 4.2 Mixed-World Benchmark Results\n',
             '',
             '## Setup',
             '- 4-obstacle mixed world: 2 DANGEROUS (UNOBSERVABLE risk=0.9) + 2 SAFE (POSITION_ONLY/FULL_STATE risk≤0.1)',
             '- 3 conditions × 2 obstacle modes × 5 seeds = 30 episodes',
             '',
             '## Results Table',
             '',
             '| condition | obs_mode | N | success% | near_coll | '
             'freeze_s | unnec_stop% | false_safe% |',
             '|-----------|----------|---|----------|-----------|'
             '---------|-------------|-------------|',
             ]

    condition_order = ['naive_baseline', 'ours_baseline', 'supervised']
    mode_order = ['static', 'moving']
    for lbl in condition_order:
        for mode in mode_order:
            key = (lbl, mode)
            grp = groups.get(key, [])
            n = len(grp)
            suc = pct(grp, 'mission_success', 1)
            near = avg(grp, 'near_collisions')
            frz = avg(grp, 'freeze_time_s')
            unst = pct(grp, 'unnecessary_stop', 1)
            fs = pct(grp, 'false_safe', 1)
            lines.append(
                f'| {lbl} | {mode} | {n} | {suc:.0f}% | {near:.1f} | '
                f'{frz:.1f}s | {unst:.0f}% | {fs:.0f}% |'
            )

    lines += [
        '',
        '## Key Metrics (averaged across static+moving)',
        '',
        '| condition | near_coll_mean | freeze_mean | collision% | unnecessary_stop% |',
        '|-----------|----------------|-------------|------------|-------------------|',
    ]
    for lbl in condition_order:
        grp_all = []
        for mode in mode_order:
            grp_all.extend(groups.get((lbl, mode), []))
        near = avg(grp_all, 'near_collisions')
        frz  = avg(grp_all, 'freeze_time_s')
        coll = pct(grp_all, 'collision', 1)
        unst = pct(grp_all, 'unnecessary_stop', 1)
        lines.append(f'| {lbl} | {near:.1f} | {frz:.1f}s | {coll:.0f}% | {unst:.0f}% |')

    lines += [
        '',
        '## Interpretation',
        '- **near_collisions** (↓ better): naive_baseline should be highest',
        '- **freeze_time_s** (tradeoff): supervised should be highest',
        '- **unnecessary_stop%**: early stops when no real obstacle within 1.0m',
        '- **false_safe%**: supervisor claimed safe but clearance < 0.6m',
        '',
        '## Source',
        f'- Script: scripts/phase42_batch.py',
        f'- Episode CSVs: {EP_DIR}/',
        f'- Episode logs: {LOG_DIR}/',
    ]

    report_path = os.path.join(OUT_DIR, 'PHASE4_2_MIXED_WORLD_BENCHMARK.md')
    with open(report_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    print(f'\n=== DONE — report: {report_path} ===')
    for l in lines:
        print(l)


if __name__ == '__main__':
    main()
