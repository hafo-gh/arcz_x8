# ARCZ - ROS 2

## Namespace

arcz

## Packages

| Package | Description |
| --- | --- |
| `arcz_connection` | Connectivity: MAVLink split/bridge to the flight controller, Zenoh DDS router, internet connectivity monitoring |
| `arcz_observability` | Observability: MCAP recording of all ROS topics while armed, Foxglove bridge for live introspection |
| `arcz_postflight` | Post-flight data collection (PX4 ULog) and resumable upload to a remote server |

## Nodes / processes

| Package | Node / process | Kind | Description |
| --- | --- | --- | --- |
| `arcz_connection` | `mavlink_bridge` | rclpy node | Bridges MAVLink messages to ROS2 topics; message-to-topic mapping is config-driven (`config/mavlink_mappings.yaml`) for Bool topics, plus a dedicated GPS_RAW_INT -> NavSatFix mirror |
| `arcz_connection` | `internet_connection` | rclpy node | Continuously TCP-probes fixed public IPs (1.1.1.1, 8.8.8.8) and publishes reachability |
| `arcz_connection` | `mavsplit` | external process (MAVProxy) | Fans the FC serial link out into UDP endpoints for QGroundControl and `mavlink_bridge` |
| `arcz_connection` | `zenoh_router` | external process (`rmw_zenohd`) | The Zenoh DDS router for this vehicle's ROS graph |
| `arcz_observability` | `mcap_recorder` | rclpy node | Records every ROS topic to MCAP while the vehicle is armed |
| `arcz_observability` | `foxglove_bridge` | external process | Foxglove Studio websocket bridge (port 8765) |
| `arcz_postflight` | `postflight_dump` (`collector_node`, `uploader_node`, `queue_status_node`) | 3 rclpy nodes | Share a durable SQLite queue: collects the PX4 ULog per qualifying flight, uploads the resulting zip via resumable tus, publishes queue depth |

## Topics currently published

| Topic | Type | Publisher | Notes |
| --- | --- | --- | --- |
| `/arcz/vehicle/is_armed` | `std_msgs/msg/Bool` | `arcz_connection` / `mavlink_bridge` | From `HEARTBEAT.base_mode` & `MAV_MODE_FLAG_SAFETY_ARMED`; more mappings can be added without code changes; transient-local reliable QoS |
| `/arcz/vehicle/is_online` | `std_msgs/msg/Bool` | `arcz_connection` / `internet_connection` | TCP-connect probe against fixed public IPs, online if any target succeeds; published every 5s (configurable); transient-local reliable QoS |
| `/arcz/location/global/fix` | `sensor_msgs/msg/NavSatFix` | `arcz_connection` / `mavlink_bridge` | Mirrors MAVLink `GPS_RAW_INT` (raw GPS fix, not the fused `GLOBAL_POSITION_INT` estimate); `fix_type` mapped to `NavSatStatus`; position covariance not populated (`COVARIANCE_TYPE_UNKNOWN`); sensor-data QoS (best-effort, volatile) |
| `/arcz/vehicle/postflight_dump/collecting` | `std_msgs/msg/UInt16` | `arcz_postflight` / `queue_status_node` | 1 Hz, active collection-queue depth |
| `/arcz/vehicle/postflight_dump/uploading` | `std_msgs/msg/UInt16` | `arcz_postflight` / `queue_status_node` | 1 Hz, active upload-queue depth |

`mcap_recorder` does not publish any topics (it only subscribes to `/arcz/vehicle/is_armed`).

The `arcz_vision` package (SIYI ZR-10 gimbal control + WebRTC video web UI) has been removed for now; its code is preserved on the `with_siyizr10` branch.

## Deployment model

Each package builds and runs as its own Docker container (`network_mode: host`, sharing a common `arcz/ros2-base` image), started via that package's own `ros2 launch` file as the container's `CMD`. `docker-compose.yml` at the repo root `include`s every package's own compose file.

`scripts/install.sh` is a plain idempotent bootstrap, not a systemd-unit generator: it copies `.env.example` to `.env` (repo root) on first run if that doesn't exist yet, removes obsolete legacy services from before this repo existed (any `*mavsplit*`/`*siyi*` systemd units), checks that `docker`/`docker compose` are installed, stops any stray `arcz_`/`ai_`/`malp_`-prefixed containers left over from manual runs, makes sure `docker.service` itself is enabled at boot (the one genuine host-level system task involved), builds the shared base image, and runs `docker compose up -d --build` from the repo root. Crash recovery is layered without any systemd wrapping of containers: ROS2 launch `respawn=True` restarts a dead process, and Docker's own `restart: unless-stopped` policy restarts a dead container or brings it back when the Docker daemon starts after a reboot.

## Configuration

Per-vehicle values that need changing live in `.env` at the repo root (copied from `.env.example` -- `ROS_DISTRO`, `ROS_DOMAIN_ID`, `PX4_SERIAL_DEVICE`, `PX4_SERIAL_BAUD`, `MALP_UPLOAD_TOKEN`), consumed by every container automatically since `docker compose` loads `.env` from the working directory it's run in. `arcz_connection`'s serial launch args (`serial_device`/`serial_baud`) are injected from there via a `command:` override in its `docker-compose.yml`, so `launch/connection.launch.py` itself never needs editing. The mavsplit UDP fan-out ports (`qgc_out_uri`/`pth_out_uri`) are considered internal wiring between `arcz_connection` and `arcz_postflight`/`mavlink_bridge` and are not meant to be reconfigured per vehicle. The one config that isn't in `.env` is `src/arcz_postflight/config/postflight_dump.yaml` (`vehicle_id`, `upload.endpoint`/`upload.probe_host`), since those are structured/nested rather than flat key-value.
