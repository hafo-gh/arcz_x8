"""Publish persistent collection and upload queue sizes at 1 Hz."""
import os

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import UInt16

from arcz_postflight.postflight_dump import store as st
from arcz_postflight.postflight_dump.config import Config


COLLECTING_TOPIC = '/arcz/postflight/collecting'
UPLOADING_TOPIC = '/arcz/postflight/uploading'
PUBLISH_PERIOD_S = 1.0
UINT16_MAX = (1 << 16) - 1


class QueueStatusNode(Node):

    def __init__(self):
        super().__init__('queue_status_node')
        self.declare_parameter('config_file', '')
        cfg_path = self.get_parameter('config_file').value or None
        self.config = Config(cfg_path)
        self.store = st.Store(os.path.join(self.config.data_root, 'state.db'))

        qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.collecting_publisher = self.create_publisher(
            UInt16, COLLECTING_TOPIC, qos)
        self.uploading_publisher = self.create_publisher(
            UInt16, UPLOADING_TOPIC, qos)
        self.timer = self.create_timer(PUBLISH_PERIOD_S, self.publish_sizes)

        # Publish the initial state immediately instead of waiting one period.
        self.publish_sizes()
        self.get_logger().info(
            'Queue status up. publishing at %.1f Hz: %s and %s'
            % (1.0 / PUBLISH_PERIOD_S, COLLECTING_TOPIC, UPLOADING_TOPIC))

    @staticmethod
    def _message(count):
        message = UInt16()
        message.data = min(max(0, int(count)), UINT16_MAX)
        return message

    def publish_sizes(self):
        collecting, uploading = self.store.queue_sizes()
        self.collecting_publisher.publish(self._message(collecting))
        self.uploading_publisher.publish(self._message(uploading))

    def destroy_node(self):
        try:
            self.store.close()
        except Exception:
            pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = QueueStatusNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
