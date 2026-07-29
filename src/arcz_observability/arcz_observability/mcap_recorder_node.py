"""Start and stop MCAP rosbag recording from the vehicle armed state."""

from datetime import datetime, timezone
from pathlib import Path
import signal
import subprocess
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool


ARMED_TOPIC = '/arcz/vehicle/is_armed'
DEFAULT_OUTPUT_DIRECTORY = '/mcap_logs'


def recording_path(output_directory: str) -> Path:
    """Return a unique, UTC timestamped output directory for one recording."""
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%SZ')
    return Path(output_directory) / f'arcz-{timestamp}'


class McapRecorderNode(Node):
    """Record every ROS topic into MCAP only while the vehicle is armed."""

    def __init__(self) -> None:
        super().__init__('mcap_recorder_node')
        self.declare_parameter('output_directory', DEFAULT_OUTPUT_DIRECTORY)
        self._output_directory = self.get_parameter('output_directory').value
        self._recorder: Optional[subprocess.Popen] = None

        armed_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self._subscription = self.create_subscription(
            Bool, ARMED_TOPIC, self._armed_callback, armed_qos
        )
        self.get_logger().info(f'Waiting for armed state on {ARMED_TOPIC}')

    def _armed_callback(self, message: Bool) -> None:
        if message.data:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self) -> None:
        if self._recorder is not None and self._recorder.poll() is None:
            return

        destination = recording_path(self._output_directory)
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = [
            'ros2', 'bag', 'record', '--all', '--storage', 'mcap',
            '--output', str(destination),
        ]
        self._recorder = subprocess.Popen(command)
        self.get_logger().info(f'Started MCAP recording: {destination}')

    def _stop_recording(self) -> None:
        if self._recorder is None:
            return
        if self._recorder.poll() is None:
            self.get_logger().info('Stopping MCAP recording')
            self._recorder.send_signal(signal.SIGINT)
            try:
                self._recorder.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.get_logger().warning('Recorder did not stop; terminating it')
                self._recorder.terminate()
                self._recorder.wait(timeout=5)
        self._recorder = None

    def destroy_node(self) -> bool:
        self._stop_recording()
        return super().destroy_node()


def main(args=None) -> None:
    """Run the MCAP logger controller."""
    rclpy.init(args=args)
    node = McapRecorderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
