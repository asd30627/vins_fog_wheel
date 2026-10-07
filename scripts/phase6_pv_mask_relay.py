#!/usr/bin/env python3
"""Phase 6.3 — PV-validity image masking relay for ORB-SLAM3.

Subscribes to stereo images + object validity detections.
Publishes masked images where invalid/dynamic regions are zeroed.

Usage (with synthetic proxy mask for EuRoC):
  python3 phase6_pv_mask_relay.py --synthetic-mask

Usage (with bbox validity from detection topic):
  python3 phase6_pv_mask_relay.py --validity-topic /paper2/object_validity
"""
import sys, os, argparse, json
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSPresetProfiles
from sensor_msgs.msg import Image
import numpy as np

try:
    from cv_bridge import CvBridge
    import cv2
    CV_OK = True
except ImportError:
    CV_OK = False


class PVMaskRelay(Node):
    """Image masking relay: zeros bbox regions where object validity < threshold."""

    def __init__(self, use_synthetic=False, validity_threshold=0.5):
        super().__init__('pv_mask_relay')
        self.bridge = CvBridge() if CV_OK else None
        self.use_synthetic = use_synthetic
        self.validity_thr = validity_threshold
        self.frame_count = 0
        self.masked_count = 0

        qos = QoSPresetProfiles.SENSOR_DATA.value

        self.sub_left = self.create_subscription(
            Image, '/cam0/image_raw', self._cb_left, qos)
        self.sub_right = self.create_subscription(
            Image, '/cam1/image_raw', self._cb_right, qos)

        self.pub_left = self.create_publisher(Image, '/cam0/image_masked', qos)
        self.pub_right = self.create_publisher(Image, '/cam1/image_masked', qos)

        self.current_bboxes = []  # [(x1,y1,x2,y2)] to mask

        if use_synthetic:
            # Synthetic: mask a fixed 100×100 region to verify masking doesn't break tracking
            # (at center-right of 752×480 EuRoC frames — typically texture-rich region)
            self.current_bboxes = [(500, 150, 650, 300)]
            self.get_logger().info('PV-Mask relay: SYNTHETIC mode (1 fixed bbox)')
        else:
            try:
                from vision_msgs.msg import Detection2DArray
                self.sub_validity = self.create_subscription(
                    Detection2DArray, '/paper2/object_validity',
                    self._cb_validity, 10)
                self.get_logger().info('PV-Mask relay: validity-topic mode')
            except ImportError:
                self.get_logger().warn('vision_msgs not found; falling back to synthetic mode')
                self.current_bboxes = [(500, 150, 650, 300)]

        self.get_logger().info(
            f'PV-Mask relay ready. threshold={validity_threshold}. '
            f'Left: /cam0/image_raw → /cam0/image_masked')

    def _cb_validity(self, msg):
        bboxes = []
        for det in msg.detections:
            score = det.results[0].hypothesis.score if det.results else 1.0
            if score < self.validity_thr:
                cx = det.bbox.center.position.x
                cy = det.bbox.center.position.y
                w  = det.bbox.size_x
                h  = det.bbox.size_y
                bboxes.append((int(cx - w/2), int(cy - h/2),
                               int(cx + w/2), int(cy + h/2)))
        self.current_bboxes = bboxes

    def _mask_image(self, msg):
        if not CV_OK:
            return msg
        img = self.bridge.imgmsg_to_cv2(msg, desired_encoding='passthrough')
        if len(self.current_bboxes) > 0:
            for (x1, y1, x2, y2) in self.current_bboxes:
                x1 = max(0, x1); y1 = max(0, y1)
                x2 = min(img.shape[1], x2); y2 = min(img.shape[0], y2)
                if x2 > x1 and y2 > y1:
                    img[y1:y2, x1:x2] = 0
            self.masked_count += 1
        self.frame_count += 1
        if self.frame_count % 100 == 0:
            self.get_logger().info(
                f'Processed {self.frame_count} frames, {self.masked_count} masked')
        return self.bridge.cv2_to_imgmsg(img, encoding=msg.encoding)

    def _cb_left(self, msg):
        masked = self._mask_image(msg)
        masked.header = msg.header
        self.pub_left.publish(masked)

    def _cb_right(self, msg):
        masked = self._mask_image(msg)
        masked.header = msg.header
        self.pub_right.publish(masked)


def main():
    parser = argparse.ArgumentParser(description='PV-validity image masking relay')
    parser.add_argument('--synthetic-mask', action='store_true',
                        help='Use a fixed synthetic bbox mask (for testing)')
    parser.add_argument('--validity-threshold', type=float, default=0.5)
    args, ros_args = parser.parse_known_args()

    rclpy.init(args=ros_args)
    node = PVMaskRelay(
        use_synthetic=args.synthetic_mask,
        validity_threshold=args.validity_threshold
    )
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
