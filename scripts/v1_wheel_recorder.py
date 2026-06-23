#!/usr/bin/env python3
# Step 3 V1: side-record the ACTUAL /wheel/delta the player publishes on the wire, to compare against the
# player's dump (value-layer bit-identical check). Reliable QoS + large depth so nothing is dropped at pb3.0.
# Writes 'ts_ns,x,y,z' with repr() (exact round-trippable doubles); x/y/z = received msg.vector.x/y/z.
import sys, rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from geometry_msgs.msg import Vector3Stamped

class Rec(Node):
    def __init__(self, out):
        super().__init__('v1_wheel_recorder')
        qos = QoSProfile(depth=500000, reliability=ReliabilityPolicy.RELIABLE, history=HistoryPolicy.KEEP_LAST)
        self.f = open(out, 'w'); self.n = 0
        self.create_subscription(Vector3Stamped, '/wheel/delta', self.cb, qos)
    def cb(self, msg):
        ts_ns = msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec
        self.f.write('%d,%r,%r,%r\n' % (ts_ns, msg.vector.x, msg.vector.y, msg.vector.z))
        self.n += 1
        if self.n % 20000 == 0: self.f.flush()

def main():
    out = sys.argv[1]
    rclpy.init()
    node = Rec(out)
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        node.f.flush(); node.f.close()
        node.get_logger().info(f'V1 recorder: wrote {node.n} /wheel/delta msgs -> {out}')
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()

if __name__ == '__main__': main()
