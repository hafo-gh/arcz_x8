from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node


def generate_launch_description():
    mcap_recorder_node = Node(
        package='arcz_observability',
        executable='mcap_recorder_node',
        name='mcap_recorder',
        parameters=[{'output_directory': '/mcap_logs'}],
        respawn=True,
        respawn_delay=1.0,
        output='screen',
    )

    # External tool: no custom node, just start it alongside ours.
    # respawn=True: this container's only crash recovery below the whole
    # process tree is ROS2 launch itself (Docker only restarts the whole
    # container if launch's own PID 1 dies).
    foxglove_bridge = ExecuteProcess(
        cmd=['ros2', 'launch', 'foxglove_bridge', 'foxglove_bridge_launch.xml', 'port:=8765'],
        respawn=True,
        respawn_delay=1.0,
        output='screen',
    )

    return LaunchDescription([
        mcap_recorder_node,
        foxglove_bridge,
    ])
