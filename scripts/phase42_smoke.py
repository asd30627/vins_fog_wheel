#!/usr/bin/env python3
"""Smoke test: naive_baseline (risk_margin_gain=0) to verify collision with y=0 obstacles."""
import subprocess, os, time, signal, csv

OUT_DIR  = '/home/ivlab3/fwvio_estimator_ws_wheel/logs/phase42'
LOG_DIR  = os.path.join(OUT_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

FASTDDS_XML = '/home/ivlab3/fwvio_estimator_ws_wheel/logs/phase42/fastdds_udp_only.xml'
ROS_PRE = ('source /opt/ros/jazzy/setup.bash && '
           'source /home/ivlab3/nav2_ws/install/setup.bash && '
           'export ROS_DOMAIN_ID=77 && '
           f'export FASTRTPS_DEFAULT_PROFILES_FILE={FASTDDS_XML}')

def start_proc(cmd, log):
    with open(log, 'w') as lf:
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

def pkill_nodes():
    for pat in ['mini_world_sim', 'validity_publisher', 'validity_to_nav_adapter']:
        subprocess.run(['pkill', '-KILL', '-f', pat],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)

pkill_nodes()
# Clear stale FastDDS shm segments before starting
import glob as _glob
for _f in _glob.glob('/dev/shm/fastrtps_*'):
    try: os.remove(_f)
    except: pass

SMOKE_CSV = os.path.join(OUT_DIR, 'smoke_naive_s0.csv')
if os.path.exists(SMOKE_CSV):
    os.remove(SMOKE_CSV)

mws_cmd = (f'{ROS_PRE} && '
           'ros2 run paper2_validity_bridge mini_world_sim --ros-args '
           '-p builtin_controller:=True '
           '-p policy_label:=naive_baseline '
           f'-p output_csv:={SMOKE_CSV} '
           '-p honor_hard_stop:=False '
           '-p risk_margin_gain:=0.0 '
           '-p risk_slow_gain:=0.0 '
           '-p move_obstacles:=False '
           '-p obstacle_seed:=0 '
           '-p timeout_s:=45.0')
vp_cmd  = f'{ROS_PRE} && ros2 run paper2_validity_bridge validity_publisher --ros-args -p policy:=ours'
adp_cmd = f'{ROS_PRE} && ros2 run paper2_validity_bridge validity_to_nav_adapter'

# Start mws first; wait 3s for DDS shm init before vp+adp join the domain
p_mws = start_proc(mws_cmd, f'{LOG_DIR}/smoke_naive_mws.log')
print(f'Started mws={p_mws.pid}, waiting 3s for DDS init...')
time.sleep(3.0)
p_vp  = start_proc(vp_cmd,  f'{LOG_DIR}/smoke_naive_vp.log')
p_adp = start_proc(adp_cmd, f'{LOG_DIR}/smoke_naive_adp.log')

print(f'Started vp={p_vp.pid} adp={p_adp.pid}')
print('Waiting up to 55s...')

t0 = time.time()
while (time.time() - t0) < 55:
    if os.path.exists(SMOKE_CSV):
        try:
            with open(SMOKE_CSV) as f:
                rows = list(csv.DictReader(f))
            if rows:
                r = rows[-1]
                try:
                    elapsed = float(r.get('elapsed_s', 0))
                    # Only break on actual completion (arrived=1/timeout) not on interim writes
                    if elapsed > 43 or r.get('success') == '1':
                        print(f'CSV complete at elapsed={elapsed:.1f}s')
                        break
                except Exception:
                    pass
        except Exception:
            pass
    if p_mws.poll() is not None:
        rc = p_mws.returncode
        print(f'mws exited rc={rc}')
        break
    alive_vp  = p_vp.poll()  is None
    alive_adp = p_adp.poll() is None
    print(f't={time.time()-t0:.0f}s mws=alive vp={alive_vp} adp={alive_adp}')
    time.sleep(5)

time.sleep(2)
kill_proc(p_adp); kill_proc(p_vp); kill_proc(p_mws)
pkill_nodes()

if os.path.exists(SMOKE_CSV):
    with open(SMOKE_CSV) as f:
        rows = list(csv.DictReader(f))
    if rows:
        r = rows[-1]
        print('\nSMOKE RESULT (naive_baseline, risk_margin_gain=0):')
        for k in ['policy', 'success', 'path_length_m', 'collisions',
                  'near_collisions', 'freezing', 'freeze_time_s',
                  'hard_stop_final', 'mission_success', 'min_obstacle_clearance_m']:
            print(f'  {k} = {r.get(k, "N/A")}')
    else:
        print('CSV written but empty — sim did not complete a step')
else:
    print('No CSV written — sim failed to start or crashed before writing')
