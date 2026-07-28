#!/usr/bin/env bash
# Fresh-host bootstrap: builds the shared ROS2 base image, then generates
# and enables one systemd unit per package (each just keeps that package's
# own docker compose project up). Run after checking out this repo and
# installing Docker.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROS_DISTRO="${ROS_DISTRO:-jazzy}"

if [[ ${EUID} -ne 0 ]]; then
  exec sudo ROS_DISTRO="$ROS_DISTRO" "$0" "$@"
fi

docker build -t "arcz/ros2-base:${ROS_DISTRO}" \
  --build-arg "ROS_DISTRO=${ROS_DISTRO}" \
  "$REPO_ROOT/docker/base"

installed=()
for compose_file in "$REPO_ROOT"/src/*/docker-compose.yml; do
  [ -e "$compose_file" ] || continue
  package_dir="$(dirname "$compose_file")"
  package_name="$(basename "$package_dir")"
  unit="/etc/systemd/system/arcz-${package_name}.service"

  cat > "$unit" <<UNIT
[Unit]
Description=ARCZ ${package_name} (docker compose)
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${package_dir}
ExecStart=/usr/bin/docker compose up -d --build
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
UNIT

  installed+=("arcz-${package_name}.service")
done

systemctl daemon-reload
for unit in "${installed[@]}"; do
  systemctl enable --now "$unit"
done

echo "Installed and started: ${installed[*]}"
