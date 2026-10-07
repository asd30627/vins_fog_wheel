#!/usr/bin/env python3
"""Test: run vp + adp only (no mws) for 10s to see if ExternalShutdownException is a startup issue."""
import subprocess, os, time, signal

ROS_PRE = ('source /opt/ros/jazzy/setup.bash && '
           'source /home/ivlab3/nav2_ws/install/setup.bash && '
           'export ROS_DOMAIN_ID=77')
LOG_DIR = '/home/ivlab3/fwvio_estimator_ws_wheel/logs/phase42/logs'
os.makedirs(LOG_DIR, exist_ok=True)

for pat in ['mini_world_sim', 'validity_publisher', 'validity_to_nav_adapter']:
    subprocess.run(['pkill', '-KILL', '-f', pat], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.5)

vp_cmd  = f'{ROS_PRE} && ros2 run paper2_validity_bridge validity_publisher --ros-args -p policy:=ours'
adp_cmd = f'{ROS_PRE} && ros2 run paper2_validity_bridge validity_to_nav_adapter'

with open(f'{LOG_DIR}/solo_vp.log', 'w') as lf:
    p_vp = subprocess.Popen(['bash', '-c', vp_cmd], stdout=lf, stderr=lf, preexec_fn=os.setsid)
with open(f'{LOG_DIR}/solo_adp.log', 'w') as lf:
    p_adp = subprocess.Popen(['bash', '-c', adp_cmd], stdout=lf, stderr=lf, preexec_fn=os.setsid)

print(f'Started vp={p_vp.pid} adp={p_adp.pid}')
print('Waiting 10s...')
t0 = time.time()
while time.time() - t0 < 10:
    vp_alive  = p_vp.poll()  is None
    adp_alive = p_adp.poll() is None
    print(f't={time.time()-t0:.1f}s vp_alive={vp_alive} adp_alive={adp_alive}')
    if not vp_alive and not adp_alive:
        print('BOTH DIED early')
        break
    time.sleep(2)

try:
    os.killpg(os.getpgid(p_vp.pid),  signal.SIGTERM)
    os.killpg(os.getpgid(p_adp.pid), signal.SIGTERM)
except: pass

print('\n=== VP LOG ===')
os.system(f'cat {LOG_DIR}/solo_vp.log | tail -5')
print('\n=== ADP LOG ===')
os.system(f'cat {LOG_DIR}/solo_adp.log | tail -5')
