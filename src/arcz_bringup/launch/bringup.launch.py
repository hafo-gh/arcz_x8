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

    # observability and vision launches will be added here once those
    # packages have nodes.

    return LaunchDescription([
        connection_launch,
    ])
