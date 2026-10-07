#!/usr/bin/env python3
"""Test mws node alone (no vp/adp) for 15s to diagnose early shutdown."""
import subprocess, os, time, signal, csv

ROS_PRE = ('source /opt/ros/jazzy/setup.bash && '
           'source /home/ivlab3/nav2_ws/install/setup.bash && '
           'export ROS_DOMAIN_ID=77')
SOLO_CSV = '/home/ivlab3/fwvio_estimator_ws_wheel/logs/phase42/smoke_mws_solo.csv'
LOG = '/home/ivlab3/fwvio_estimator_ws_wheel/logs/phase42/logs/smoke_mws_solo.log'

for pat in ['mini_world_sim', 'validity_publisher', 'validity_to_nav_adapter']:
    subprocess.run(['pkill', '-KILL', '-f', pat], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)

cmd = (f'{ROS_PRE} && '
       'ros2 run paper2_validity_bridge mini_world_sim --ros-args '
       '-p builtin_controller:=True '
       '-p policy_label:=naive_baseline '
       f'-p output_csv:={SOLO_CSV} '
       '-p honor_hard_stop:=False '
       '-p risk_margin_gain:=0.0 '
       '-p risk_slow_gain:=0.0 '
       '-p move_obstacles:=False '
       '-p obstacle_seed:=0 '
       '-p timeout_s:=15.0')

with open(LOG, 'w') as lf:
    p = subprocess.Popen(['bash', '-c', cmd], stdout=lf, stderr=lf, preexec_fn=os.setsid)

print(f'mws solo PID={p.pid}, waiting up to 20s for 15s episode...')
t0 = time.time()
while time.time() - t0 < 20:
    if p.poll() is not None:
        print(f'mws exited at t={time.time()-t0:.1f}s rc={p.returncode}')
        break
    if os.path.exists(SOLO_CSV):
        try:
            rows = list(csv.DictReader(open(SOLO_CSV)))
            if rows and float(rows[-1].get('elapsed_s', 0)) >= 14:
                print(f'mws completed episode at t={time.time()-t0:.1f}s')
                break
        except:
            pass
    time.sleep(1)

try:
    os.killpg(os.getpgid(p.pid), signal.SIGTERM)
    p.wait(timeout=3)
except:
    pass

print('\n=== MWS LOG ===')
os.system(f'cat {LOG}')
print('\n=== CSV ===')
if os.path.exists(SOLO_CSV):
    os.system(f'cat {SOLO_CSV}')
else:
    print('NO CSV')
