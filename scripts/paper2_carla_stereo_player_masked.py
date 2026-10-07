#!/usr/bin/env python3
"""Paper-2 Part 2 / Phase C — CARLA stereo+IMU player with optional DYNAMIC-OBJECT FEATURE SUPPRESSION.

Faithful copy of fwvio_ws/scripts/carla_stereo_player.py + a single addition: --mask-json.
--mask-json points to {frame_int: [[x0,y0,x1,y1], ...]} pixel bboxes to SUPPRESS in the LEFT image
(VINS-Fusion tracks features on cam0/left). Suppression = heavy in-place Gaussian blur of each bbox
region (kills Shi-Tomasi corners there) with NO hard black-box boundary (boundary stays low-contrast).
No --mask-json => byte-identical behavior to the stock baseline player.

Pure-file replay; does NOT touch the CARLA service. Same topics/timing as the stock player so VINS sees
an identical stream except for the suppressed regions.
"""
import os, sys, glob, json, argparse, time
import numpy as np, cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, Imu
from geometry_msgs.msg import Vector3Stamped
from rosgraph_msgs.msg import Clock
from cv_bridge import CvBridge


def load_imu(rec, fname):
    p = f"{rec}/{fname}"
    if not os.path.exists(p): return None
    a = np.loadtxt(p, delimiter=',', skiprows=1)
    return a[a[:, 0].argsort()]


def suppress_regions(img, boxes, blur_ksize=31, dilate=4):
    """Blur each bbox region in-place to remove corners (feature suppression). Soft, no hard edge."""
    h, w = img.shape[:2]
    for (x0, y0, x1, y1) in boxes:
        x0 = max(0, int(x0) - dilate); y0 = max(0, int(y0) - dilate)
        x1 = min(w, int(x1) + dilate); y1 = min(h, int(y1) + dilate)
        if x1 <= x0 + 2 or y1 <= y0 + 2:
            continue
        roi = img[y0:y1, x0:x1]
        k = blur_ksize | 1  # odd
        img[y0:y1, x0:x1] = cv2.GaussianBlur(roi, (k, k), 0)
    return img


class CarlaStereoPlayer(Node):
    def __init__(self, rec, rate, drop_head, encoding, use_imu, imu_csv='imu.csv', wheel_csv=None,
                 max_frames=0, mask_json=None, stereo_mask_json=None):
        super().__init__('carla_stereo_player')
        self.bridge = CvBridge()
        self.pub_l = self.create_publisher(Image, '/carla/left/image_raw', 10)
        self.pub_r = self.create_publisher(Image, '/carla/right/image_raw', 10)
        self.pub_clk = self.create_publisher(Clock, '/clock', 10)
        self.use_imu = use_imu
        self.imu = load_imu(rec, imu_csv) if use_imu else None
        self.imu_i = 0
        self.pub_imu = self.create_publisher(Imu, '/carla/imu', 200) if use_imu else None
        if use_imu: self.get_logger().info(f"IMU: {0 if self.imu is None else len(self.imu)} samples")
        self.wheel = load_imu(rec, wheel_csv) if wheel_csv else None
        self.wheel_i = 0
        self.pub_wheel = self.create_publisher(Vector3Stamped, '/wheel/delta', 200) if wheel_csv else None
        if wheel_csv: self.get_logger().info(f"WHEEL: {0 if self.wheel is None else len(self.wheel)} samples")
        self.masks = {}
        if mask_json:
            raw = json.load(open(mask_json))
            self.masks = {int(k): v for k, v in raw.items()}
            nb = sum(len(v) for v in self.masks.values())
            self.get_logger().info(f"MASK: {len(self.masks)} frames, {nb} boxes from {os.path.basename(mask_json)}")
        # stereo mask (repair 2026-07-02): {frame: {"L":[...],"R":[...]}}, blur BOTH images so stereo
        # matching is fair (masking left-only would leave the object in the right image).
        self.smasks = {}
        if stereo_mask_json:
            raw = json.load(open(stereo_mask_json))
            self.smasks = {int(k): v for k, v in raw.items()}
            nl = sum(len(v.get('L', [])) for v in self.smasks.values())
            nr = sum(len(v.get('R', [])) for v in self.smasks.values())
            self.get_logger().info(f"STEREO-MASK: {len(self.smasks)} frames, L={nl} R={nr} boxes from {os.path.basename(stereo_mask_json)}")
        frames = sorted(int(os.path.basename(p)[:-4]) for p in glob.glob(f"{rec}/stereo_left/*.png"))
        frames = frames[drop_head:]
        if max_frames and max_frames > 0:
            frames = frames[:max_frames]
        self.rec, self.frames, self.rate, self.enc = rec, frames, rate, encoding
        self.get_logger().info(f"player: {len(frames)} frames (dropped head {drop_head}), rate={rate}, enc={encoding}")

    def ts_of(self, fi):
        try:
            return json.load(open(f"{self.rec}/gt/{fi:06d}.json"))["ts_ns"]
        except Exception:
            return fi * 50_000_000

    def run(self):
        dt_wall = 0.05 / max(self.rate, 1e-3)
        for fi in self.frames:
            if not rclpy.ok(): break
            ts = self.ts_of(fi)
            li = cv2.imread(f"{self.rec}/stereo_left/{fi:06d}.png")
            ri = cv2.imread(f"{self.rec}/stereo_right/{fi:06d}.png")
            if li is None or ri is None: continue
            boxes = self.masks.get(fi, [])
            if boxes:
                li = suppress_regions(li, boxes)   # suppress dynamic-object features in LEFT (cam0)
            sm = self.smasks.get(fi)
            if sm:                                 # stereo-consistent: blur BOTH images
                if sm.get('L'): li = suppress_regions(li, sm['L'])
                if sm.get('R'): ri = suppress_regions(ri, sm['R'])
            if self.enc == 'mono8':
                li = cv2.cvtColor(li, cv2.COLOR_BGR2GRAY); ri = cv2.cvtColor(ri, cv2.COLOR_BGR2GRAY)
            sec, nsec = int(ts // 1_000_000_000), int(ts % 1_000_000_000)
            clk = Clock(); clk.clock.sec = sec; clk.clock.nanosec = nsec; self.pub_clk.publish(clk)
            if self.imu is not None:
                while self.imu_i < len(self.imu) and self.imu[self.imu_i, 0] <= ts:
                    s = self.imu[self.imu_i]; self.imu_i += 1
                    m = Imu(); isec, insec = int(s[0] // 1e9), int(s[0] % 1e9)
                    m.header.stamp.sec = isec; m.header.stamp.nanosec = insec; m.header.frame_id = 'imu'
                    m.linear_acceleration.x, m.linear_acceleration.y, m.linear_acceleration.z = s[1], s[2], s[3]
                    m.angular_velocity.x, m.angular_velocity.y, m.angular_velocity.z = s[4], s[5], s[6]
                    self.pub_imu.publish(m); time.sleep(0.001)
            if self.wheel is not None:
                while self.wheel_i < len(self.wheel) and self.wheel[self.wheel_i, 0] <= ts:
                    w = self.wheel[self.wheel_i]; self.wheel_i += 1
                    wm = Vector3Stamped(); wsec, wnsec = int(w[0] // 1e9), int(w[0] % 1e9)
                    wm.header.stamp.sec = wsec; wm.header.stamp.nanosec = wnsec
                    wm.vector.x, wm.vector.y, wm.vector.z = w[1], w[2], w[3]
                    self.pub_wheel.publish(wm); time.sleep(0.001)
            ml = self.bridge.cv2_to_imgmsg(li, encoding=self.enc); mr = self.bridge.cv2_to_imgmsg(ri, encoding=self.enc)
            for m in (ml, mr):
                m.header.stamp.sec = sec; m.header.stamp.nanosec = nsec; m.header.frame_id = 'cam'
            self.pub_l.publish(ml); self.pub_r.publish(mr)
            time.sleep(dt_wall)
        self.get_logger().info("player: done publishing all frames")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rec', required=True)
    ap.add_argument('--rate', type=float, default=0.5)
    ap.add_argument('--drop-head', type=int, default=0)
    ap.add_argument('--encoding', default='mono8', choices=['mono8', 'bgr8'])
    ap.add_argument('--imu', action='store_true')
    ap.add_argument('--imu-csv', default='imu.csv')
    ap.add_argument('--wheel-csv', default=None)
    ap.add_argument('--max-frames', type=int, default=0)
    ap.add_argument('--mask-json', default=None, help='per-frame bboxes to suppress in LEFT image')
    ap.add_argument('--stereo-mask-json', default=None, help='{frame:{L:[...],R:[...]}} blur BOTH images (fair stereo mask)')
    a = ap.parse_args()
    rclpy.init()
    node = CarlaStereoPlayer(a.rec, a.rate, a.drop_head, a.encoding, a.imu, a.imu_csv, a.wheel_csv,
                             a.max_frames, a.mask_json, a.stereo_mask_json)
    try:
        node.run()
    finally:
        node.destroy_node(); rclpy.shutdown()


if __name__ == '__main__':
    main()
