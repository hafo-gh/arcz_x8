"""Manages internet connectivity. Implementation TODO."""
import rclpy
from rclpy.node import Node


class InternetConnectionNode(Node):

    def __init__(self):
        super().__init__('internet_connection')
        self.get_logger().warn('internet_connection is not implemented yet')


def main():
    rclpy.init()
    node = InternetConnectionNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
