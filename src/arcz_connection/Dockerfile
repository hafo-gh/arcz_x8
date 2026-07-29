ARG ROS_DISTRO=jazzy
FROM arcz/ros2-base:${ROS_DISTRO}

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /ros2_ws/src/arcz_connection
COPY . .

# MAVProxy is not a rosdep/apt package; the rest (rmw_zenoh_cpp,
# pymavlink, PyYAML) resolves straight from package.xml.
RUN apt-get update \
    && rosdep install --from-paths . --ignore-src -r -y \
    && rm -rf /var/lib/apt/lists/*
RUN pip3 install --no-cache-dir --break-system-packages MAVProxy future

WORKDIR /ros2_ws
RUN . "/opt/ros/${ROS_DISTRO}/setup.sh" && colcon build --symlink-install

CMD ["ros2", "launch", "arcz_connection", "connection.launch.py"]
