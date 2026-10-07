#!/usr/bin/env python3
"""Publish a KITTI Odometry sequence's grayscale stereo pair (image_0/image_1) as ROS2 topics for
ORB-SLAM3 stereo -- shared image host for SemanticKITTI (which supplies only semantic/instance
labels + velodyne, not its own images). Mirrors kitti_tracking_stereo_player.py's pattern
(e2 real-data smoke, 2026-07-04).
  usage: e2_kitti_odometry_stereo_player.py --seq-dir <.../sequences/00> --rate 0.5
"""
import argparse, glob, os, time
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
import cv2
from cv_bridge import CvBridge


class KittiOdometryStereoPlayer(Node):
    def __init__(self, base, rate):
        super().__init__('kitti_odometry_stereo_player')
        self.bridge = CvBridge()
        self.pub_l = self.create_publisher(Image, '/kittiodom/left', 10)
        self.pub_r = self.create_publisher(Image, '/kittiodom/right', 10)
        self.ld = f"{base}/image_0"
        self.rd = f"{base}/image_1"
        self.frames = sorted(int(os.path.basename(p)[:-4]) for p in glob.glob(f"{self.ld}/*.png"))
        self.rate = rate
        self.get_logger().info(f"KITTI odometry {base}: {len(self.frames)} frames, rate={rate}")

    def run(self):
        dt = 0.1 / max(self.rate, 1e-3)
        for fi in self.frames:
            if not rclpy.ok():
                break
            lp = f"{self.ld}/{fi:06d}.png"
            rp = f"{self.rd}/{fi:06d}.png"
            limg = cv2.imread(lp, cv2.IMREAD_COLOR)
            rimg = cv2.imread(rp, cv2.IMREAD_COLOR)
            if limg is None or rimg is None:
                continue
            stamp = self.get_clock().now().to_msg()
            lmsg = self.bridge.cv2_to_imgmsg(limg, encoding='bgr8')
            rmsg = self.bridge.cv2_to_imgmsg(rimg, encoding='bgr8')
            lmsg.header.stamp = stamp
            rmsg.header.stamp = stamp
            lmsg.header.frame_id = 'kittiodom_left'
            rmsg.header.frame_id = 'kittiodom_right'
            self.pub_l.publish(lmsg)
            self.pub_r.publish(rmsg)
            rclpy.spin_once(self, timeout_sec=0.0)
            time.sleep(dt)
        self.get_logger().info("KITTI odometry player: done")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq-dir", required=True)
    ap.add_argument("--rate", type=float, default=0.5)
    args = ap.parse_args()
    rclpy.init()
    node = KittiOdometryStereoPlayer(args.seq_dir, args.rate)
    node.run()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
