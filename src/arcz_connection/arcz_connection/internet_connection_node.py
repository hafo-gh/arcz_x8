"""Continuously checks internet reachability and publishes it as a bool topic.

Reachability is decided by plain TCP-connect probes (no ICMP -- needs raw
sockets/root and is often blocked anyway; no HTTP GET -- heavier than needed)
against a small set of well-known public IP:port targets, chosen by fixed IP
so the check does not itself depend on DNS resolution. The link counts as
online if *any* one target succeeds, so one blocked/down provider does not
produce a false negative.
"""
import socket
import threading

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool

ONLINE_TOPIC = '/arcz/vehicle/is_online'

# Cloudflare and Google public DNS, probed on their DNS port. Any host that
# reliably accepts TCP connections would do; these two are chosen for being
# well-known, stable, and reachable by fixed IP.
DEFAULT_TARGETS = [
    '1.1.1.1:53',
    '8.8.8.8:53',
]

# Transient-local + reliable so a subscriber started after us still gets the
# current state immediately instead of waiting for the next poll.
ONLINE_QOS = QoSProfile(
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
)


def _probe(target, timeout_s):
    host, _, port = target.rpartition(':')
    try:
        with socket.create_connection((host, int(port)), timeout=timeout_s):
            return True
    except OSError:
        return False


class InternetConnectionNode(Node):

    def __init__(self):
        super().__init__('internet_connection')
        self.declare_parameter('poll_interval_s', 5.0)
        self.declare_parameter('timeout_s', 2.0)
        self.declare_parameter('targets', DEFAULT_TARGETS)

        self.poll_interval = float(self.get_parameter('poll_interval_s').value)
        self.timeout_s = float(self.get_parameter('timeout_s').value)
        self.targets = list(self.get_parameter('targets').value)

        self._publisher = self.create_publisher(Bool, ONLINE_TOPIC, ONLINE_QOS)

        self._online = None
        self._stop = threading.Event()
        self._worker = threading.Thread(target=self._poll_loop, daemon=True)
        self._worker.start()
        self.get_logger().info(
            'internet_connection up. probing %s every %.1fs'
            % (self.targets, self.poll_interval))

    def _check_online(self):
        return any(_probe(target, self.timeout_s) for target in self.targets)

    def _poll_loop(self):
        while not self._stop.is_set():
            online = self._check_online()
            if online != self._online:
                self._online = online
                self.get_logger().info(
                    'Internet %s' % ('online' if online else 'offline'))
            self._publisher.publish(Bool(data=online))
            self._stop.wait(timeout=self.poll_interval)

    def destroy_node(self):
        self._stop.set()
        if self._worker.is_alive():
            self._worker.join(timeout=5.0)
        super().destroy_node()


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
