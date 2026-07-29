"""Bridges mavlink messages (via pymavlink) onto ros2 topics."""
import os

import yaml
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import NavSatFix, NavSatStatus
from std_msgs.msg import Bool
from pymavlink import mavutil
from ament_index_python.packages import get_package_share_directory

# Transient-local + reliable so a subscriber started after us (e.g. another
# container) still gets the latest value immediately instead of waiting for
# the next mavlink message.
TOPIC_QOS = QoSProfile(
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
)

DEFAULT_MAPPINGS = [
    {
        'mavlink_msg': 'HEARTBEAT',
        'field': 'base_mode',
        'bitmask': 'MAV_MODE_FLAG_SAFETY_ARMED',
        'topic': '/arcz/vehicle/is_armed',
    },
]

GPS_FIX_TOPIC = '/arcz/location/global/fix'

# GPS_RAW_INT.fix_type (MAV_GPS_FIX_TYPE) -> NavSatStatus.status.
_FIX_TYPE_TO_STATUS = {
    0: NavSatStatus.STATUS_NO_FIX,    # GPS_FIX_TYPE_NO_GPS
    1: NavSatStatus.STATUS_NO_FIX,    # GPS_FIX_TYPE_NO_FIX
    2: NavSatStatus.STATUS_FIX,       # GPS_FIX_TYPE_2D_FIX
    3: NavSatStatus.STATUS_FIX,       # GPS_FIX_TYPE_3D_FIX
    4: NavSatStatus.STATUS_GBAS_FIX,  # GPS_FIX_TYPE_DGPS
    5: NavSatStatus.STATUS_GBAS_FIX,  # GPS_FIX_TYPE_RTK_FLOAT
    6: NavSatStatus.STATUS_GBAS_FIX,  # GPS_FIX_TYPE_RTK_FIXED
    7: NavSatStatus.STATUS_GBAS_FIX,  # GPS_FIX_TYPE_STATIC
    8: NavSatStatus.STATUS_GBAS_FIX,  # GPS_FIX_TYPE_PPP
}


class MavlinkBridgeNode(Node):

    def __init__(self):
        super().__init__('mavlink_bridge')
        self.declare_parameter('connection', 'udpin:127.0.0.1:14552')
        self.declare_parameter('mappings_file', '')

        connection = self.get_parameter('connection').value
        self.get_logger().info(f'Connecting to mavlink at {connection}')
        self.mav = mavutil.mavlink_connection(connection)

        self._topic_entries = {}
        self._load_mappings(self.get_parameter('mappings_file').value)

        # Raw GPS fix (GPS_RAW_INT), not part of the generic Bool/bitmask
        # mapping mechanism above since it's a different message type built
        # from several fields at once.
        self._gps_fix_publisher = self.create_publisher(
            NavSatFix, GPS_FIX_TOPIC, qos_profile_sensor_data)

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

            publisher = self.create_publisher(Bool, mapping['topic'], TOPIC_QOS)
            self._topic_entries.setdefault(mapping['mavlink_msg'], []).append(
                (publisher, mapping))
            self.get_logger().info(
                f"Mirroring {mapping['mavlink_msg']}.{mapping['field']} -> {mapping['topic']}")

    def _poll(self):
        msg = self.mav.recv_match(blocking=False)
        while msg is not None:
            msg_type = msg.get_type()
            for publisher, mapping in self._topic_entries.get(msg_type, []):
                value = getattr(msg, mapping['field'])
                if mapping['bitmask'] is not None:
                    value = bool(value & mapping['bitmask'])
                else:
                    value = bool(value)
                publisher.publish(Bool(data=value))
            if msg_type == 'GPS_RAW_INT':
                self._publish_gps_fix(msg)
            msg = self.mav.recv_match(blocking=False)

    def _publish_gps_fix(self, msg):
        fix = NavSatFix()
        fix.header.stamp = self.get_clock().now().to_msg()
        fix.header.frame_id = 'gps'
        fix.status.status = _FIX_TYPE_TO_STATUS.get(
            msg.fix_type, NavSatStatus.STATUS_NO_FIX)
        fix.status.service = NavSatStatus.SERVICE_GPS
        fix.latitude = msg.lat / 1e7
        fix.longitude = msg.lon / 1e7
        fix.altitude = msg.alt / 1e3
        fix.position_covariance_type = NavSatFix.COVARIANCE_TYPE_UNKNOWN
        self._gps_fix_publisher.publish(fix)


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
