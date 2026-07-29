"""Launch all post-flight nodes. Optionally pass config_file:=/path/to.yaml."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    config_file = LaunchConfiguration('config_file')

    collector = Node(
        package='arcz_postflight',
        executable='collector_node',
        name='malp_postflight_collector',
        parameters=[{'config_file': config_file}],
        respawn=True,
        respawn_delay=1.0,
        output='screen',
    )
    uploader = Node(
        package='arcz_postflight',
        executable='uploader_node',
        name='malp_postflight_uploader',
        parameters=[{'config_file': config_file}],
        respawn=True,
        respawn_delay=1.0,
        output='screen',
    )
    queue_status = Node(
        package='arcz_postflight',
        executable='queue_status_node',
        name='malp_postflight_queue_status',
        parameters=[{'config_file': config_file}],
        respawn=True,
        respawn_delay=1.0,
        output='screen',
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'config_file', default_value='',
            description='Path to postflight_dump.yaml (empty = installed default).'),
        collector,
        uploader,
        queue_status,
    ])
