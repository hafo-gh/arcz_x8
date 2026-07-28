import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    connection_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory('arcz_connection'),
                         'launch', 'connection.launch.py')
        )
    )

    vision_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory('arcz_vision'),
                         'launch', 'vision.launch.py')
        )
    )

    # observability launch will be added here once that package has nodes.

    return LaunchDescription([
        connection_launch,
        vision_launch,
    ])
