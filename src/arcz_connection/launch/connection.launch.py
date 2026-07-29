import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('arcz_connection')

    serial_device = LaunchConfiguration('serial_device')
    serial_baud = LaunchConfiguration('serial_baud')
    qgc_out_uri = LaunchConfiguration('qgc_out_uri')
    pth_out_uri = LaunchConfiguration('pth_out_uri')

    # External tools: no custom node, just start them alongside ours.
    # respawn=True: this container's only crash recovery below the whole
    # process tree is ROS2 launch itself (Docker only restarts the whole
    # container if launch's own PID 1 dies).
    zenoh_router = ExecuteProcess(
        cmd=['ros2', 'run', 'rmw_zenoh_cpp', 'rmw_zenohd'],
        respawn=True,
        respawn_delay=1.0,
        output='screen',
    )

    # mavsplit = MAVProxy fanning the FC serial link out to a UDP port for
    # QGroundControl and a UDP port for mavlink_bridge. MAVProxy connects
    # OUT to pth_out_uri, so mavlink_bridge must be listening there.
    mavsplit = ExecuteProcess(
        cmd=[
            'mavproxy.py',
            ['--master=', serial_device, ',', serial_baud],
            ['--out=', qgc_out_uri],
            ['--out=', pth_out_uri],
            '--non-interactive',
        ],
        respawn=True,
        respawn_delay=1.0,
        output='screen',
    )

    mavlink_bridge_node = Node(
        package='arcz_connection',
        executable='mavlink_bridge_node',
        name='mavlink_bridge_node',
        parameters=[os.path.join(pkg_share, 'config', 'mavlink_bridge.yaml')],
        respawn=True,
        respawn_delay=1.0,
        output='screen',
    )

    internet_connection_node = Node(
        package='arcz_connection',
        executable='internet_connection_node',
        name='internet_connection_node',
        respawn=True,
        respawn_delay=1.0,
        output='screen',
    )

    return LaunchDescription([
        DeclareLaunchArgument('serial_device', default_value='/dev/ttyACM0'),
        DeclareLaunchArgument('serial_baud', default_value='921600'),
        DeclareLaunchArgument('qgc_out_uri', default_value='udpin:0.0.0.0:14551'),
        DeclareLaunchArgument('pth_out_uri', default_value='udpout:127.0.0.1:14552'),
        zenoh_router,
        mavsplit,
        mavlink_bridge_node,
        internet_connection_node,
    ])
