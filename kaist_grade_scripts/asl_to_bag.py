#!/usr/bin/env python3
# Convert an EuRoC ASL sequence (mav0/) to a ROS2 (jazzy) rosbag2 sqlite3 bag.
# Topics match the existing MH_03/V1_02 bags: /cam0/image_raw, /cam1/image_raw (mono8), /imu0.
# Timestamps come straight from the ASL ns columns. Memory-light: images are read from disk and
# serialized at write time (not all buffered). Usage: asl_to_bag.py <mav0_dir> <out_bag_dir>
import sys, os, csv, cv2
import rosbag2_py
from rclpy.serialization import serialize_message
from sensor_msgs.msg import Image, Imu
from std_msgs.msg import Header

mav0, outdir = sys.argv[1], sys.argv[2]
if os.path.exists(outdir):
    sys.exit(f"out bag dir already exists: {outdir}")

def stamp(ns):
    h = Header(); h.stamp.sec = int(ns // 1_000_000_000); h.stamp.nanosec = int(ns % 1_000_000_000)
    return h

def img_bytes(ns, path, frame):
    im = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if im is None: return None
    m = Image(); m.header = stamp(ns); m.header.frame_id = frame
    m.height, m.width = im.shape; m.encoding = "mono8"
    m.is_bigendian = 0; m.step = int(im.shape[1]); m.data = im.tobytes()
    return serialize_message(m)

def imu_bytes(ns, v):
    m = Imu(); m.header = stamp(ns); m.header.frame_id = "imu0"
    m.angular_velocity.x, m.angular_velocity.y, m.angular_velocity.z = v[0], v[1], v[2]
    m.linear_acceleration.x, m.linear_acceleration.y, m.linear_acceleration.z = v[3], v[4], v[5]
    m.orientation_covariance = [-1.0] + [0.0]*8
    return serialize_message(m)

# Build a lightweight event index (ns, kind, payload-ref) — NO serialized bytes held.
# kind: 'c0'/'c1' payload=image path ; 'imu' payload=6 floats
events = []
for cam, kind in (("cam0","c0"), ("cam1","c1")):
    with open(os.path.join(mav0, cam, "data.csv")) as f:
        for row in csv.reader(f):
            if not row or row[0].startswith("#"): continue
            ns = int(row[0]); events.append((ns, kind, os.path.join(mav0, cam, "data", row[1].strip())))
with open(os.path.join(mav0, "imu0", "data.csv")) as f:
    for row in csv.reader(f):
        if not row or row[0].startswith("#"): continue
        ns = int(row[0]); events.append((ns, "imu", [float(x) for x in row[1:7]]))

events.sort(key=lambda e: e[0])
print(f"  events: {len(events)} (sorted by ts)")

writer = rosbag2_py.SequentialWriter()
writer.open(rosbag2_py.StorageOptions(uri=outdir, storage_id="sqlite3"),
            rosbag2_py.ConverterOptions("", ""))
TOP = {"c0": ("/cam0/image_raw","sensor_msgs/msg/Image"),
       "c1": ("/cam1/image_raw","sensor_msgs/msg/Image"),
       "imu": ("/imu0","sensor_msgs/msg/Imu")}
for topic, typ in TOP.values():
    writer.create_topic(rosbag2_py.TopicMetadata(name=topic, type=typ, serialization_format="cdr", id=0))

n_img = n_imu = 0
for ns, kind, payload in events:
    if kind == "imu":
        writer.write("/imu0", imu_bytes(ns, payload), ns); n_imu += 1
    else:
        b = img_bytes(ns, payload, "cam0" if kind=="c0" else "cam1")
        if b is not None: writer.write(TOP[kind][0], b, ns); n_img += 1
del writer
print(f"  wrote bag -> {outdir}  (images={n_img}, imu={n_imu})")
