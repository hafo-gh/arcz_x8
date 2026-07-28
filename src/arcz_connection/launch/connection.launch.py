import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('arcz_connection')

    # External packages: no custom node, just start them alongside ours.
    zenoh_router = ExecuteProcess(
        cmd=['ros2', 'run', 'rmw_zenoh_cpp', 'rmw_zenohd'],
        output='screen',
    )

    foxglove_bridge = ExecuteProcess(
        cmd=['ros2', 'launch', 'foxglove_bridge', 'foxglove_bridge_launch.xml', 'port:=8765'],
        output='screen',
    )

    mavsplit_node = Node(
        package='arcz_connection',
        executable='mavsplit_node',
        name='mavsplit',
        parameters=[os.path.join(pkg_share, 'config', 'mavsplit.yaml')],
        output='screen',
    )

    mavlink_bridge_node = Node(
        package='arcz_connection',
        executable='mavlink_bridge_node',
        name='mavlink_bridge',
        parameters=[os.path.join(pkg_share, 'config', 'mavlink_bridge.yaml')],
        output='screen',
    )

    internet_connection_node = Node(
        package='arcz_connection',
        executable='internet_connection_node',
        name='internet_connection',
        output='screen',
    )

    return LaunchDescription([
        zenoh_router,
        foxglove_bridge,
        mavsplit_node,
        mavlink_bridge_node,
        internet_connection_node,
    ])
