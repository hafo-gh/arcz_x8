ARG ROS_DISTRO=jazzy
FROM arcz/ros2-base:${ROS_DISTRO}

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /ros2_ws/src/arcz_observability
COPY . .

RUN apt-get update \
    && rosdep install --from-paths . --ignore-src -r -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /ros2_ws
RUN . "/opt/ros/${ROS_DISTRO}/setup.sh" && colcon build --symlink-install

CMD ["ros2", "launch", "arcz_observability", "observability.launch.py"]
