ARG ROS_DISTRO=jazzy
FROM arcz/ros2-base:${ROS_DISTRO}

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /ros2_ws/src/arcz_postflight
COPY . .

# rosdep's python3-pymavlink key doesn't actually land a working pymavlink
# in this base image (silently skipped by 'rosdep install -r'), so install
# it directly via pip, same as arcz_connection does for MAVProxy.
RUN apt-get update     && rosdep install --from-paths . --ignore-src -r -y     && rm -rf /var/lib/apt/lists/*
RUN pip3 install --no-cache-dir --break-system-packages pymavlink

WORKDIR /ros2_ws
RUN . "/opt/ros/${ROS_DISTRO}/setup.sh" && colcon build --symlink-install

CMD ["ros2", "launch", "arcz_postflight", "postflight.launch.py"]
