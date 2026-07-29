# ARCZ - ROS 2

## Namespace

arcz

## Packages

| Package | Description |
| --- | --- |
| `arcz_connection` | Connectivity: MAVLink split/bridge to the flight controller, Zenoh DDS router, internet connectivity monitoring |
| `arcz_observability` | Observability: MCAP recording of all ROS topics while armed, Foxglove bridge for live introspection |
| `arcz_postflight` | Post-flight data collection (PX4 ULog + matching mcap recording) and resumable upload to a remote server |

## Nodes / processes

| Package | Node / process | Kind | Description |
| --- | --- | --- | --- |
| `arcz_connection` | `mavlink_bridge` | rclpy node | Bridges MAVLink messages to ROS2 topics; message-to-topic mapping is config-driven (`config/mavlink_mappings.yaml`) for Bool topics, plus a dedicated GPS\_RAW\_INT -> NavSatFix mirror |
| `arcz_connection` | `internet_connection` | rclpy node | Continuously TCP-probes fixed public IPs (1.1.1.1, 8.8.8.8) and publishes reachability |
| `arcz_connection` | `mavsplit` | external process (MAVProxy) | Fans the FC serial link out into UDP endpoints for QGroundControl and `mavlink_bridge` |
| `arcz_connection` | `zenoh_router` | external process (`rmw_zenohd`) | The Zenoh DDS router for this vehicle’s ROS graph |
| `arcz_observability` | `mcap_recorder` | rclpy node | Records every ROS topic to MCAP while the vehicle is armed |
| `arcz_observability` | `foxglove_bridge` | external process | Foxglove Studio websocket bridge (port 8765) |
| `arcz_postflight` | `postflight_dump` (`collector_node`, `uploader_node`, `queue_status_node`) | 3 rclpy nodes | Share a durable SQLite queue: collects the PX4 ULog and the matching `arcz_observability` mcap recording per qualifying flight, uploads the resulting zip via resumable tus, publishes queue depth |

## Topics currently published

| Topic | Type | Publisher | Notes |
| --- | --- | --- | --- |
| `/arcz/vehicle/is_armed` | `std_msgs/msg/Bool` | `arcz_connection` / `mavlink_bridge` | From `HEARTBEAT.base_mode` & `MAV_MODE_FLAG_SAFETY_ARMED`; more mappings can be added without code changes; transient-local reliable QoS |
| `/arcz/vehicle/is_online` | `std_msgs/msg/Bool` | `arcz_connection` / `internet_connection` | TCP-connect probe against fixed public IPs, online if any target succeeds; published every 5s (configurable); transient-local reliable QoS |
| `/arcz/location/global/fix` | `sensor_msgs/msg/NavSatFix` | `arcz_connection` / `mavlink_bridge` | Mirrors MAVLink `GPS_RAW_INT` (raw GPS fix, not the fused `GLOBAL_POSITION_INT` estimate); `fix_type` mapped to `NavSatStatus`; position covariance not populated (`COVARIANCE_TYPE_UNKNOWN`); sensor-data QoS (best-effort, volatile) |
| `/arcz/vehicle/postflight_dump/collecting` | `std_msgs/msg/UInt16` | `arcz_postflight` / `queue_status_node` | 1 Hz, active collection-queue depth |
| `/arcz/vehicle/postflight_dump/uploading` | `std_msgs/msg/UInt16` | `arcz_postflight` / `queue_status_node` | 1 Hz, active upload-queue depth |

`mcap_recorder` does not publish any topics (it only subscribes to `/arcz/vehicle/is_armed`).