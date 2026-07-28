ARG ROS_DISTRO=jazzy
FROM arcz/ros2-base:${ROS_DISTRO}

ENV DEBIAN_FRONTEND=noninteractive

# Vendored MediaMTX binary, pinned the same way the original arcz_siyi
# install.sh did (arm64 build for the Jetson Orin).
ARG MEDIAMTX_VERSION=1.19.1
ARG MEDIAMTX_SHA256=97a277cf24153e168008c18da53fe84e8d364456e2d7b457dc0457666c32867
RUN curl -fL --retry 5 --retry-delay 2 \
      "https://github.com/bluenviron/mediamtx/releases/download/v${MEDIAMTX_VERSION}/mediamtx_v${MEDIAMTX_VERSION}_linux_arm64.tar.gz" \
      -o /tmp/mediamtx.tar.gz \
    && echo "${MEDIAMTX_SHA256}  /tmp/mediamtx.tar.gz" | sha256sum --check --status \
    && tar -xzf /tmp/mediamtx.tar.gz -C /usr/local/bin mediamtx \
    && rm /tmp/mediamtx.tar.gz

WORKDIR /ros2_ws/src/arcz_vision
COPY . .

RUN apt-get update \
    && rosdep install --from-paths . --ignore-src -r -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /ros2_ws
RUN . "/opt/ros/${ROS_DISTRO}/setup.sh" && colcon build --symlink-install

CMD ["ros2", "launch", "arcz_vision", "vision.launch.py"]
