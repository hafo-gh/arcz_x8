"""Splits the FC serial connection into multiple UDP mavlink endpoints."""
import rclpy
from rclpy.node import Node
from pymavlink import mavutil


class MavSplitNode(Node):

    def __init__(self):
        super().__init__('mavsplit')
        self.declare_parameter('serial_port', '/dev/ttyTHS0')
        self.declare_parameter('serial_baud', 921600)
        self.declare_parameter('udp_endpoints', [
            'udpin:0.0.0.0:14551',
            'udpin:127.0.0.1:14552',
        ])

        serial_port = self.get_parameter('serial_port').value
        serial_baud = self.get_parameter('serial_baud').value
        udp_endpoints = self.get_parameter('udp_endpoints').value

        self.get_logger().info(f'Connecting to FC on {serial_port} @ {serial_baud}')
        self.fc_conn = mavutil.mavlink_connection(serial_port, baud=serial_baud)

        self.udp_conns = []
        for endpoint in udp_endpoints:
            self.get_logger().info(f'Opening split endpoint {endpoint}')
            self.udp_conns.append(mavutil.mavlink_connection(endpoint))

        self.timer = self.create_timer(0.005, self._poll)

    def _poll(self):
        msg = self.fc_conn.recv_msg()
        while msg is not None:
            buf = msg.get_msgbuf()
            for conn in self.udp_conns:
                conn.write(buf)
            msg = self.fc_conn.recv_msg()

        for conn in self.udp_conns:
            msg = conn.recv_msg()
            while msg is not None:
                self.fc_conn.write(msg.get_msgbuf())
                msg = conn.recv_msg()


def main():
    rclpy.init()
    node = MavSplitNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
