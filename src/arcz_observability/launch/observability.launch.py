from launch import LaunchDescription
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

    return LaunchDescription([
        mcap_recorder_node,
    ])
