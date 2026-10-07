#!/usr/bin/env python3
"""Publish a KITTI-360 sequence's rectified perspective stereo pair (image_00/image_01, already
rectified 'data_rect' images) as ROS2 topics for ORB-SLAM3 stereo, mirroring the pattern of
kitti_tracking_stereo_player.py (E2 real-data smoke, 2026-07-04).
  usage: e2_kitti360_stereo_player.py --seq-dir <.../raw/2013_05_28_drive_0003_sync/extracted/2013_05_28_drive_0003_sync> --rate 0.5
"""
import argparse, glob, os
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
import cv2
from cv_bridge import CvBridge


class Kitti360StereoPlayer(Node):
    def __init__(self, base, rate):
        super().__init__('kitti360_stereo_player')
        self.bridge = CvBridge()
        self.pub_l = self.create_publisher(Image, '/kitti360/left', 10)
        self.pub_r = self.create_publisher(Image, '/kitti360/right', 10)
        self.ld = f"{base}/image_00/data_rect"
        self.rd = f"{base}/image_01/data_rect"
        self.frames = sorted(int(os.path.basename(p)[:-4]) for p in glob.glob(f"{self.ld}/*.png"))
        self.rate = rate
        self.get_logger().info(f"KITTI-360 {base}: {len(self.frames)} frames, rate={rate}")

    def run(self):
        dt = 0.1 / max(self.rate, 1e-3)
        for fi in self.frames:
            if not rclpy.ok():
                break
            lp = f"{self.ld}/{fi:010d}.png"
            rp = f"{self.rd}/{fi:010d}.png"
            limg = cv2.imread(lp, cv2.IMREAD_COLOR)
            rimg = cv2.imread(rp, cv2.IMREAD_COLOR)
            if limg is None or rimg is None:
                continue
            stamp = self.get_clock().now().to_msg()
            lmsg = self.bridge.cv2_to_imgmsg(limg, encoding='bgr8')
            rmsg = self.bridge.cv2_to_imgmsg(rimg, encoding='bgr8')
            lmsg.header.stamp = stamp
            rmsg.header.stamp = stamp
            lmsg.header.frame_id = 'kitti360_left'
            rmsg.header.frame_id = 'kitti360_right'
            self.pub_l.publish(lmsg)
            self.pub_r.publish(rmsg)
            rclpy.spin_once(self, timeout_sec=0.0)
            import time
            time.sleep(dt)
        self.get_logger().info("KITTI-360 player: done")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq-dir", required=True, help=".../extracted/<seq_name> dir with image_00/image_01 subdirs")
    ap.add_argument("--rate", type=float, default=0.5)
    args = ap.parse_args()
    rclpy.init()
    node = Kitti360StereoPlayer(args.seq_dir, args.rate)
    node.run()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
