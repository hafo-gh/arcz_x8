"""Bridges mavlink messages (via pymavlink) onto ros2 topics."""
import os

import yaml
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool
from pymavlink import mavutil
from ament_index_python.packages import get_package_share_directory

DEFAULT_MAPPINGS = [
    {
        'mavlink_msg': 'HEARTBEAT',
        'field': 'base_mode',
        'bitmask': 'MAV_MODE_FLAG_SAFETY_ARMED',
        'topic': '/arcz/vehicle/is_armed',
    },
]


class MavlinkBridgeNode(Node):

    def __init__(self):
        super().__init__('mavlink_bridge')
        self.declare_parameter('connection', 'udpout:127.0.0.1:14552')
        self.declare_parameter('mappings_file', '')

        connection = self.get_parameter('connection').value
        self.get_logger().info(f'Connecting to mavlink at {connection}')
        self.mav = mavutil.mavlink_connection(connection)

        self._topic_entries = {}
        self._load_mappings(self.get_parameter('mappings_file').value)

        self.timer = self.create_timer(0.01, self._poll)

    def _load_mappings(self, mappings_file):
        mappings = DEFAULT_MAPPINGS
        if mappings_file:
            if not os.path.isabs(mappings_file):
                mappings_file = os.path.join(
                    get_package_share_directory('arcz_connection'), mappings_file)
            with open(mappings_file) as f:
                mappings = yaml.safe_load(f)['mappings']

        for mapping in mappings:
            bitmask = mapping.get('bitmask')
            if bitmask:
                bitmask = getattr(mavutil.mavlink, bitmask)
            mapping = {**mapping, 'bitmask': bitmask}

            publisher = self.create_publisher(Bool, mapping['topic'], 10)
            self._topic_entries.setdefault(mapping['mavlink_msg'], []).append(
                (publisher, mapping))
            self.get_logger().info(
                f"Mirroring {mapping['mavlink_msg']}.{mapping['field']} -> {mapping['topic']}")

    def _poll(self):
        msg = self.mav.recv_match(blocking=False)
        while msg is not None:
            for publisher, mapping in self._topic_entries.get(msg.get_type(), []):
                value = getattr(msg, mapping['field'])
                if mapping['bitmask'] is not None:
                    value = bool(value & mapping['bitmask'])
                else:
                    value = bool(value)
                publisher.publish(Bool(data=value))
            msg = self.mav.recv_match(blocking=False)


def main():
    rclpy.init()
    node = MavlinkBridgeNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
