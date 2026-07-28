import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    pkg_share = get_package_share_directory('arcz_vision')

    mediamtx_binary = LaunchConfiguration('mediamtx_binary')
    mediamtx_config = LaunchConfiguration('mediamtx_config')
    web_root = LaunchConfiguration('web_root')
    health_file = LaunchConfiguration('health_file')
    port = LaunchConfiguration('port')
    bind_loopback = LaunchConfiguration('bind_loopback')
    bind_tailscale = LaunchConfiguration('bind_tailscale')

    # MediaMTX is a vendored external binary (fetched at image build time),
    # same treatment as zenoh_router/foxglove_bridge in arcz_connection.
    # respawn=True: this container's only crash recovery below the whole
    # process tree is ROS2 launch itself (Docker only restarts the whole
    # container if launch's own PID 1 dies).
    mediamtx = ExecuteProcess(
        cmd=[mediamtx_binary, mediamtx_config],
        respawn=True,
        respawn_delay=1.0,
        output='screen',
    )

    # zr10_gateway serves the web UI, proxies WHEP signalling to MediaMTX,
    # and exposes the gimbal control REST API backed by siyi_protocol.
    zr10_gateway = ExecuteProcess(
        cmd=[
            'zr10_gateway',
            '--bind', bind_loopback,
            '--bind', bind_tailscale,
            '--port', port,
            '--web-root', web_root,
            '--health-file', health_file,
        ],
        respawn=True,
        respawn_delay=1.0,
        output='screen',
    )

    # zr10_healthcheck was a systemd oneshot run every 3s by a timer, and
    # restarted stuck systemd services by name. Under Docker there is no
    # such thing to restart from in here (a stuck process gets restarted
    # by respawn=True above, a stuck container by Docker's own restart
    # policy), so this loop now only reports health.json.
    zr10_healthcheck = ExecuteProcess(
        cmd=['bash', '-c', [
            'while true; do zr10_healthcheck --output ', health_file, '; sleep 3; done',
        ]],
        respawn=True,
        respawn_delay=1.0,
        output='screen',
    )

    return LaunchDescription([
        DeclareLaunchArgument('mediamtx_binary', default_value='mediamtx'),
        DeclareLaunchArgument(
            'mediamtx_config',
            default_value=os.path.join(pkg_share, 'config', 'zr10_mediamtx.yml')),
        DeclareLaunchArgument(
            'web_root', default_value=os.path.join(pkg_share, 'web')),
        DeclareLaunchArgument(
            'health_file', default_value='/tmp/arcz_vision_zr10_health.json'),
        DeclareLaunchArgument('port', default_value='8080'),
        # bind_tailscale defaults to this vehicle's current Tailscale address,
        # matching the live deployment; override per-vehicle as needed.
        DeclareLaunchArgument('bind_loopback', default_value='127.0.0.1'),
        DeclareLaunchArgument('bind_tailscale', default_value='100.99.9.62'),
        mediamtx,
        zr10_gateway,
        zr10_healthcheck,
    ])
