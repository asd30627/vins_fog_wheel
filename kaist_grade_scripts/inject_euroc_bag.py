#!/usr/bin/env python3
"""Inject inertial GRADE degradation onto an EuRoC ros2 bag's /imu0 gyro, mirroring the KAIST
xsens injection (gen_kaist_grade_xsens.inject) EXACTLY (gyro-only, Allan ARW/bias/BRW/scale).

PURE DATA-LAYER: images + all other topics are byte-copied (raw, no re-deserialize); only /imu0
angular_velocity is replaced with the degraded measurement. Estimator/binary untouched.

Two-pass, low-RAM: pass1 deserializes ONLY imu -> full gyro array -> inject(); pass2 streams the
bag again writing raw bytes for non-imu and re-serialized degraded imu (same read order).

Usage: python3 inject_euroc_bag.py --bag <in_bagdir> --out <out_bagdir> --grade industrial_fog [--seed 42]
"""
import argparse, math, os, sys
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message, serialize_message
from sensor_msgs.msg import Imu

DEG2RAD = math.pi/180.0
PROFILES = {  # identical to gen_kaist_grade_xsens.PROFILES
    "industrial_fog": dict(arw=0.03, bias=0.3,  brw=0.005, scale_ppm=200),
    "precision_mems": dict(arw=0.15, bias=5.0,  brw=0.05,  scale_ppm=1000),
    "general_imu":    dict(arw=0.3,  bias=10.0, brw=0.1,   scale_ppm=2000),
}

def inject(ts_s, gyr_clean, prof, seed):
    """Identical to gen_kaist_grade_xsens.inject(): rate-domain gyro Allan injection."""
    arw = prof["arw"]*DEG2RAD/60.0
    bias_sig = prof["bias"]*DEG2RAD/3600.0
    brw_den = prof["brw"]*DEG2RAD/3600.0
    scale_sig = prof["scale_ppm"]*1e-6
    rng = np.random.RandomState(int(seed))
    const_bias = rng.randn(3)*bias_sig
    scale_err = rng.randn(3)*scale_sig
    n = len(ts_s)
    dts = np.diff(ts_s, prepend=ts_s[0]); dts[0] = (ts_s[1]-ts_s[0]) if n>1 else 1e-3
    dts = np.maximum(dts, 1e-6)
    wn = rng.randn(n,3)*(arw/np.sqrt(dts))[:,None]
    brw = np.cumsum(brw_den*np.sqrt(dts)[:,None]*rng.randn(n,3), axis=0)
    return (1.0+scale_err)*gyr_clean + const_bias + brw + wn

def reader(bagdir):
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=bagdir, storage_id='sqlite3'),
           rosbag2_py.ConverterOptions('', ''))
    return r

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bag', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--grade', required=True, choices=list(PROFILES))
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--imu_topic', default='/imu0')
    ap.add_argument('--scale', type=float, default=1.0,
                    help='knife-edge: multiply all Allan params (arw/bias/brw/scale_ppm) by this factor. '
                         'Default 1.0 = stock grade (matrix behaviour unchanged).')
    a = ap.parse_args()
    if os.path.exists(a.out):
        print(f"[skip] out exists: {a.out}"); return
    prof = {k: v*a.scale for k, v in PROFILES[a.grade].items()}

    # pass 1: collect imu gyro + ts (in read order)
    r = reader(a.bag)
    ts=[]; gyr=[]
    while r.has_next():
        topic, data, t = r.read_next()
        if topic == a.imu_topic:
            m = deserialize_message(data, Imu)
            ts.append(m.header.stamp.sec + m.header.stamp.nanosec*1e-9)
            gyr.append([m.angular_velocity.x, m.angular_velocity.y, m.angular_velocity.z])
    del r
    ts = np.array(ts); gyr = np.array(gyr)
    gyr_inj = inject(ts, gyr, prof, a.seed)
    cn=np.linalg.norm(gyr,axis=1); mn=np.linalg.norm(gyr_inj,axis=1)
    wn_std=prof["arw"]*DEG2RAD/60.0/np.sqrt(0.005)
    print(f"[inj] {os.path.basename(a.bag)}/{a.grade} x{a.scale:g}: imu_n={len(ts)} "
          f"clean|g|med={np.median(cn):.3e} meas|g|med={np.median(mn):.3e} "
          f"wn_std={wn_std:.3e} (gyr_n_model=1.0e-2)")

    # pass 2: stream-write, raw-copy non-imu, re-serialize degraded imu
    r = reader(a.bag)
    topics = r.get_all_topics_and_types()
    w = rosbag2_py.SequentialWriter()
    w.open(rosbag2_py.StorageOptions(uri=a.out, storage_id='sqlite3'),
           rosbag2_py.ConverterOptions('', ''))
    for tm in topics:
        w.create_topic(tm)  # pass source TopicMetadata through (preserves id/qos/hash)
    k=0
    while r.has_next():
        topic, data, t = r.read_next()
        if topic == a.imu_topic:
            m = deserialize_message(data, Imu)
            m.angular_velocity.x = float(gyr_inj[k,0])
            m.angular_velocity.y = float(gyr_inj[k,1])
            m.angular_velocity.z = float(gyr_inj[k,2])
            k+=1
            w.write(topic, serialize_message(m), t)
        else:
            w.write(topic, data, t)
    del w, r
    assert k==len(ts), f"imu count mismatch {k}!={len(ts)}"
    print(f"[ok] wrote {a.out}")

if __name__=='__main__':
    main()
