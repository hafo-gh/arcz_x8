# ARCZ - ROS 2

## Namespace

arcz

## Packages

| Package | Descirption |
| --- | --- |
| `arcz_connection` | | 
| `arcz_observability` | | 
| `arcz_vision` | | 
| `arcz_navigation` | | 

## Nodes

| Package | Node | Description |
| --- | --- | --- |
| `arcz_connection` | `mavsplit` | | 
| `arcz_connection` | `mavlink_bridge` | | 
| `arcz_connection` | `foxglove_bridge` | | 
| `arcz_connection` | `zenoh_router` | | 
| `arcz_connection` | `internet_connection` | | 
| `arcz_observability` | `mcap_recorder` | | 
| `arcz_observability` | `postflight_dump` | | 
| `arcz_vision` | `zr10_bridge` | | 



## Complete topic list

| Topic | Type | Publisher | Rate | Prod |
| --- | --- | --- | --- | --- |
| **Vehicle** |  |  |  |  |
| `/arcz/state/armed` | `std_msgs/msg/Bool` | `arcz_vehicle / mavlink_bridge` | 50 | ✓ |
| `/arcz/state/online` | `std_msgs/msg/Bool` | `arcz_malp / internet` | 1 | ✓ |
| `/arcz/state/mcap_recording` | `std_msgs/msg/Bool` |  |  |  |
| `/arcz/state/postflight_dump/collecting` | `std_msgs/msg/UInt16` | `arcz_malp / postflight_dump` | 1 | ✓ |
| `/arcz/state/postflight_dump/uploading` | `std_msgs/msg/UInt16` | `arcz_malp / postflight_dump` | 1 | ✓ |
| `/arcz/position/global/fix` | `sensor_msgs/msg/NavSatFix` | `arcz_vehicle / mavlink_bridge` | 10 | ✓ |






## Backup topics from older nodes

| Topic | Type | Publisher Package | Rate | Prod |
| --- | --- | --- | --- | --- |
| **Diagnostics** |  |  |  |  |
| `/diagnostics` | `diagnostic_msgs/msg/DiagnosticArray` | `arcz_diagnostic` (multiple nodes) | configurable | — |
| `/arcz/diagnostics/status` | `diagnostic_msgs/msg/DiagnosticArray` | `arcz_diagnostic` | configurable | — |
| **Point to home** |  |  |  |  |
| `/arcz/point_to_home/altitude_error_m` | `std_msgs/msg/Float32` | `arcz_point_to_home` |  | ☓ |
| `/arcz/point_to_home/current_relative_altitude_m` | `std_msgs/msg/Float32` | `arcz_point_to_home` |  | ☓ |
| `/arcz/point_to_home/estimated_speed_mps` | `std_msgs/msg/Float32` | `arcz_point_to_home` |  | ☓ |
| `/arcz/point_to_home/global_position` | `sensor_msgs/msg/NavSatFix` | `arcz_point_to_home` |  | ☓ |
| `/arcz/point_to_home/ground_truth_course_home` | `std_msgs/msg/Float32` | `arcz_point_to_home` |  | ☓ |
| `/arcz/point_to_home/ground_truth_speed_mps` | `std_msgs/msg/Float32` | `arcz_point_to_home` |  | ☓ |
| `/arcz/point_to_home/is_armed` | `std_msgs/msg/Bool` | `arcz_point_to_home` |  | ☓ |
| `/arcz/point_to_home/is_bag_recording` | `std_msgs/msg/Bool` | `arcz_point_to_home` |  | ☓ |
| `/arcz/point_to_home/offboard_state` | `std_msgs/msg/String` | `arcz_point_to_home` |  | ✓ |
| `/arcz/point_to_home/return_heading` | `std_msgs/msg/Float32` | `arcz_point_to_home` |  | ☓ |
| `/arcz/point_to_home/return_heading_weight` | `std_msgs/msg/Float32` | `arcz_point_to_home` |  | ☓ |
| `/arcz/point_to_home/setpoint_heading_deg` | `std_msgs/msg/Float32` | `arcz_point_to_home` |  | ✓ |
| `/arcz/point_to_home/setpoint_pitch_deg` | `std_msgs/msg/Float32` | `arcz_point_to_home` |  | ✓ |
| `/arcz/point_to_home/setpoint_thrust` | `std_msgs/msg/Float32` | `arcz_point_to_home` |  | ✓ |
| `/arcz/point_to_home/target_altitude_m` | `std_msgs/msg/Float32` | `arcz_point_to_home` |  | ✓ |
| `/arcz/point_to_home/throttle_pid/clamped_thrust` | `std_msgs/msg/Float32` | `arcz_point_to_home` |  | ☓ |
| `/arcz/point_to_home/throttle_pid/kd_term` | `std_msgs/msg/Float32` | `arcz_point_to_home` |  | ☓ |
| `/arcz/point_to_home/throttle_pid/kp_term` | `std_msgs/msg/Float32` | `arcz_point_to_home` |  | ☓ |
| `/arcz/point_to_home/throttle_pid/trim_thrust` | `std_msgs/msg/Float32` | `arcz_point_to_home` |  | ☓ |
| `/arcz/point_to_home/throttle_pid/unclamped_thrust` | `std_msgs/msg/Float32` | `arcz_point_to_home` |  | ☓ |
| `/arcz/point_to_home/throttle_pid/vertical_speed_mps` | `int32std_msgs/msg/Float32` | `arcz_point_to_home` |  | ☓ |
| **External data: weather** |  |  |  |  |
| `/arcz/external/weather/metar_raw` | `std_msgs/msg/String` | `arcz_data_service` | 0.01 / on request | — |
| `/arcz/external/weather/taf_raw` | `std_msgs/msg/String` | `arcz_data_service` | 0.01 | — |
| `/arcz/external/weather/sigmet_raw` | `std_msgs/msg/String` | `arcz_data_service` | 0.01 | — |
| `/arcz/external/weather/qnh` | `sensor_msgs/msg/FluidPressure` | `arcz_data_service` | 0.1 | — |
| `/arcz/external/weather/temperature` | `sensor_msgs/msg/Temperature` | `arcz_data_service` | — | — |
| `/arcz/external/weather/dew_point` | `sensor_msgs/msg/Temperature` | `arcz_data_service` | — | — |
| `/arcz/external/weather/wind` | `arcz_msgs/msg/WindEstimate` | `arcz_data_service` | — | — |
| **Estimation** |  |  |  |  |
| `/arcz/estimation/altitude/agl` | `arcz_msgs/msg/AltitudeEstimate` | `arcz_estimator` | 5 | — |
| `/arcz/estimation/odometry/local` | `nav_msgs/msg/Odometry` | `arcz_estimator` | 30 | — |
| `/arcz/estimation/status/local` | `arcz_msgs/msg/EstimatorStatus` | `arcz_estimator` | 5 | — |
| `/arcz/estimator/global/best_fix` | `sensor_msgs/msg/NavSatFix` | `arcz_estimator` | 10 | — |
| `/arcz/estimation/status/global` | `arcz_msgs/msg/EstimatorStatus` | `arcz_estimator` | 2 | — |
| `/arcz/estimation/gnss/fix_best` | `sensor_msgs/msg/NavSatFix` | `arcz_gnss_arbiter` | 10 | — |
| `/arcz/estimation/gnss/trust` | `arcz_msgs/msg/GpsTrustStatus` | `arcz_gnss_arbiter` | 10 | — |
| `/arcz/estimation/gnss/reasoning` | `std_msgs/msg/String` | `arcz_gnss_arbiter` | 10 | — |
| **Flight-controller bridge** |  |  |  |  |
| `/arcz/fc_bridge/px4/arming_state` | `std_msgs/msg/Bool` | `arcz_fc_bridge` | MAVLink-driven | — |
| `/arcz/fc_bridge/px4/flight_mode` | `std_msgs/msg/String` | `arcz_fc_bridge` | 2 | — |
| `/arcz/fc_bridge/px4/navigation_state` | `std_msgs/msg/String` | `arcz_fc_bridge` | 2 | — |
| `/arcz/fc_bridge/px4/vehicle_attitude` | `geometry_msgs/msg/QuaternionStamped` | `arcz_fc_bridge` | MAVLink-driven | — |
| `/arcz/fc_bridge/px4/gps/raw` | `sensor_msgs/msg/NavSatFix` | `arcz_fc_bridge` | MAVLink-driven | — |
| `/arcz/fc_bridge/px4/mission/status` | `arcz_msgs/msg/FcMissionStatus` | `arcz_fc_bridge` | 2 | — |
| `/arcz/fc_bridge/px4/offboard/status` | `arcz_msgs/msg/OffboardStatus` | `arcz_fc_bridge` | 10 | — |
| `/arcz/fc_bridge/px4/vision_odometry_out` | `nav_msgs/msg/Odometry` | `arcz_fc_bridge` | 50 (when available) | — |
| `/arcz/fc_bridge/px4/timesync_offset_us` | `std_msgs/msg/Float64` | `arcz_fc_bridge` | MAVLink-driven | — |
| `/arcz/fc_bridge/px4/timesync_rtt_ms` | `std_msgs/msg/Float64` | `arcz_fc_bridge` | MAVLink-driven | — |
| `/arcz/fc_bridge/telemetry/gnss_fix` | `sensor_msgs/msg/NavSatFix` | `arcz_fc_bridge` | MAVLink-driven | — |
| `/arcz/fc_bridge/telemetry/alt_amsl` | `std_msgs/msg/Float64` | `arcz_fc_bridge` | MAVLink-driven | — |
| `/arcz/fc_bridge/telemetry/alt_surface` | `std_msgs/msg/Float64` | `arcz_fc_bridge` | MAVLink-driven | — |
| `/arcz/fc_bridge/telemetry/attitude_euler` | `geometry_msgs/msg/Vector3Stamped` | `arcz_fc_bridge` | MAVLink-driven | — |
| `/arcz/fc_bridge/telemetry/attitude_rates` | `geometry_msgs/msg/Vector3Stamped` | `arcz_fc_bridge` | MAVLink-driven | — |
| `/arcz/fc_bridge/telemetry/barometer/pressure` | `sensor_msgs/msg/FluidPressure` | `arcz_fc_bridge` | MAVLink-driven | — |
| `/arcz/fc_bridge/telemetry/is_armed` | `std_msgs/msg/Bool` | `arcz_fc_bridge` | MAVLink-driven | — |
| **Sensors / I/O** |  |  |  |  |
| `/arcz/sensors/barometer/pressure` | `sensor_msgs/msg/FluidPressure` | `arcz_io` | 10 | — |
| `/arcz/sensors/barometer/debug` | `arcz_msgs/msg/BarometerDebug` | `arcz_io` | 10 (debug enabled) | — |
| `/arcz/sensors/gnss/fix` | `sensor_msgs/msg/NavSatFix` | `arcz_io` | 5 | — |
| `/arcz/sensors/imu/data` | `sensor_msgs/msg/Imu` | `arcz_io` | 50 | — |
| `/arcz/sensors/imu/filtered` | `sensor_msgs/msg/Imu` | `arcz_io` | 50 (enabled) | — |
| `/arcz/sensors/magnetometer/magnetic_field` | `sensor_msgs/msg/MagneticField` | `arcz_io` | 10 | — |
| **Vision** |  |  |  |  |
| `/arcz/vision/camera_1/image_rect` | `sensor_msgs/msg/Image` | `arcz_vision` | input-driven | — |
| `/arcz/vision/camera_3/image_rect` | `sensor_msgs/msg/Image` | `arcz_vision` | input-driven | — |
| `/arcz/vision/camera_2/camera_info` | `sensor_msgs/msg/CameraInfo` | `arcz_vision` | input-driven | — |
| `/arcz/vision/camera_1/image_compressed` | `sensor_msgs/msg/CompressedImage` | `arcz_vision` | ≤16 | — |
| `/arcz/vision/optical_flow/tracks` | `arcz_msgs/msg/FeatureTracks` | `arcz_vision` | frame-driven | — |
| `/arcz/vision/optical_flow/twist` | `geometry_msgs/msg/TwistWithCovarianceStamped` | `arcz_vision` | frame-driven | — |
| `/arcz/vision/optical_flow/status` | `arcz_msgs/msg/EstimatorStatus` | `arcz_vision` | 10 | — |
| `/arcz/vision/segmentation/mask` | `sensor_msgs/msg/Image` | `arcz_vision` | 5 | — |
| `/arcz/vision/segmentation/labels` | `arcz_msgs/msg/SegmentationLabels` | `arcz_vision` | 5 | — |
| `/arcz/vision/segmentation/status` | `arcz_msgs/msg/EstimatorStatus` | `arcz_vision` | 1 | — |
| `/arcz/vision/geolocation/hypothesis` | `arcz_msgs/msg/GeoHypothesis` | `arcz_vision` | 1 | — |
| `/arcz/vision/geolocation/status` | `arcz_msgs/msg/EstimatorStatus` | `arcz_vision` | 1 | — |
| `/arcz/vision/optical_homography/status` | `arcz_msgs/msg/EstimatorStatus` | `arcz_vision` | 1 | — |