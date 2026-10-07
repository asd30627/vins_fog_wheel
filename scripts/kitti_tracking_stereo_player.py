#!/usr/bin/env python3
"""Publish a KITTI Tracking sequence's stereo pair as ROS2 topics for ORB-SLAM3 stereo.
Publishes /kitti/left and /kitti/right (bgr8) with synthetic 10 Hz stamps (frame*0.1 s) so they
match the oxts->TUM GT stamps. No IMU (KITTI tracking has no high-rate IMU) -> stereo mode.
  usage: kitti_tracking_stereo_player.py --seq-dir <.../training> --seq 0000 [--rate 0.5]
                                          [--blackout-start N] [--blackout-duration N]

Blackout (P0.5/G1-runtime): input-level LOST trigger. When --blackout-start >= 0, the frames in
the window [start, start+duration) are replaced (in-place, same shape/dtype) with an all-black
image so ORB-SLAM3 extracts no features and tracking goes lost -> RECENTLY_LOST -> Relocalization().
Frame indexing is by ordinal position in the sorted frame list (0-based), NOT the raw KITTI file id.
Default start=-1 (disabled) => byte-identical to the original player. Default duration=10 frames:
at the repo-standard --rate 0.5 (0.2 s/frame -> 5 fps effective) that is ~2.0 s of loss, kept safely
under ORB-SLAM3's ~3.0 s RECENTLY_LOST->LOST cutoff (Tracking.cc, ~15 frames) so the map is NOT reset.
"""
import argparse, glob, os, time
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
import cv2
from cv_bridge import CvBridge


class KittiStereoPlayer(Node):
    def __init__(self, base, seq, rate, blackout_start=-1, blackout_duration=10):
        super().__init__('kitti_stereo_player')
        self.bridge = CvBridge()
        self.pub_l = self.create_publisher(Image, '/kitti/left', 10)
        self.pub_r = self.create_publisher(Image, '/kitti/right', 10)
        self.ld = f"{base}/image_02/{seq}"
        self.rd = f"{base}/image_03/{seq}"
        self.frames = sorted(int(os.path.basename(p)[:-4]) for p in glob.glob(f"{self.ld}/*.png"))
        self.rate = rate
        self.blackout_start = blackout_start
        self.blackout_duration = blackout_duration
        self.get_logger().info(f"KITTI seq {seq}: {len(self.frames)} frames, rate={rate}")
        if blackout_start >= 0:
            self.get_logger().info(
                f"BLACKOUT enabled: ordinal frames [{blackout_start}, "
                f"{blackout_start + blackout_duration}) forced all-black")

    def run(self):
        dt = 0.1 / max(self.rate, 1e-3)
        bo_start = self.blackout_start
        bo_end = bo_start + self.blackout_duration  # exclusive
        for ordinal, fi in enumerate(self.frames):
            if not rclpy.ok():
                break
            li = cv2.imread(f"{self.ld}/{fi:06d}.png")
            ri = cv2.imread(f"{self.rd}/{fi:06d}.png")
            if li is None or ri is None:
                continue
            if bo_start >= 0 and bo_start <= ordinal < bo_end:
                # In-place all-black substitution: preserves image shape/dtype so the stereo
                # pair still publishes as a valid synced message; ORB extracts ~0 features.
                li[:] = 0
                ri[:] = 0
            ts = fi * 0.1  # synthetic 10 Hz
            sec, nsec = int(ts), int((ts - int(ts)) * 1e9)
            ml = self.bridge.cv2_to_imgmsg(li, encoding='bgr8')
            mr = self.bridge.cv2_to_imgmsg(ri, encoding='bgr8')
            for m in (ml, mr):
                m.header.stamp.sec = sec
                m.header.stamp.nanosec = nsec
                m.header.frame_id = 'cam'
            self.pub_l.publish(ml)
            self.pub_r.publish(mr)
            time.sleep(dt)
        self.get_logger().info("player: done")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seq-dir', required=True, help='.../kitti/tracking/training')
    ap.add_argument('--seq', required=True)
    ap.add_argument('--rate', type=float, default=0.5)
    ap.add_argument('--blackout-start', type=int, default=-1,
                    help='ordinal (0-based) frame index to begin all-black substitution; '
                         '-1 disables (default) => original player behavior')
    ap.add_argument('--blackout-duration', type=int, default=10,
                    help='number of consecutive frames to black out (default 10, ~2.0s @ rate 0.5)')
    a = ap.parse_args()
    rclpy.init()
    n = KittiStereoPlayer(a.seq_dir, a.seq, a.rate, a.blackout_start, a.blackout_duration)
    try:
        n.run()
    finally:
        n.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
