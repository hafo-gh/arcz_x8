#!/usr/bin/env bash
# Fresh-host bootstrap. Run after checking out this repo and installing
# Docker. Cleans up obsolete legacy services/containers from before this
# repo existed, checks dependencies, then brings the whole stack up with
# plain `docker compose up -d --build`. Docker's own `restart:
# unless-stopped` policy (plus `docker.service` being enabled at boot,
# which any Docker install already does) is what survives a reboot or a
# crashed container -- systemd is not used to wrap/supervise containers
# here, only for genuine host-level system tasks.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ${EUID} -ne 0 ]]; then
  exec sudo "$0" "$@"
fi

echo "==> Ensuring .env exists"
if [ ! -f "$REPO_ROOT/.env" ]; then
  cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
  chmod 600 "$REPO_ROOT/.env"
  echo "    created .env from .env.example -- edit it for this vehicle, see the note at the end"
else
  echo "    .env already exists, leaving it as-is"
fi

# Loaded into this script's own environment too (not just docker compose's),
# so e.g. the base-image build below uses the same ROS_DISTRO as .env sets.
set -a
# shellcheck disable=SC1091
source "$REPO_ROOT/.env"
set +a
ROS_DISTRO="${ROS_DISTRO:-jazzy}"

echo "==> Removing obsolete legacy systemd services (mavsplit/siyi)"
for pattern in '*mavsplit*' '*siyi*'; do
  while IFS= read -r unit; do
    [ -z "$unit" ] && continue
    echo "    removing: $unit"
    systemctl stop "$unit" 2>/dev/null || true
    systemctl disable "$unit" 2>/dev/null || true
    rm -f "/etc/systemd/system/$unit"
  done < <(systemctl list-unit-files "$pattern" --no-legend 2>/dev/null | awk '{print $1}')
done
systemctl daemon-reload

echo "==> Checking dependencies"
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed." >&2
  echo "Install it first, e.g.: curl -fsSL https://get.docker.com | sh" >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: the 'docker compose' plugin is not available." >&2
  echo "Install it, e.g.: apt-get install docker-compose-plugin" >&2
  exit 1
fi

echo "==> Stopping stray containers (arcz_/ai_/malp_ prefixed)"
mapfile -t stray_containers < <(docker ps -a --format '{{.Names}}' | grep -E '^(arcz_|ai_|malp_)' || true)
if [ "${#stray_containers[@]}" -gt 0 ]; then
  echo "    stopping: ${stray_containers[*]}"
  docker stop "${stray_containers[@]}"
fi

echo "==> Ensuring the Docker daemon itself starts on boot (a real system task)"
systemctl enable docker >/dev/null 2>&1 || true

echo "==> Building the shared ROS2 base image"
docker build -t "arcz/ros2-base:${ROS_DISTRO}" \
  --build-arg "ROS_DISTRO=${ROS_DISTRO}" \
  "$REPO_ROOT/docker/base"

echo "==> Bringing the stack up"
(cd "$REPO_ROOT" && docker compose up -d --build)

cat <<EOF

==> Done. Per-vehicle configuration lives in two places:

  .env (repo root, copied from .env.example above if it didn't exist yet)
      ROS_DISTRO, ROS_DOMAIN_ID, PX4_SERIAL_DEVICE, PX4_SERIAL_BAUD,
      MALP_UPLOAD_TOKEN -- picked up by every container automatically,
      no need to edit any launch/*.py file.

  src/arcz_postflight/config/postflight_dump.yaml
      vehicle_id                          - this vehicle's UUID in the mrblack database
      upload.endpoint / upload.probe_host - the mrblack server address

After editing .env, re-run this script (or just
"docker compose up -d --build" from the repo root) to apply changes.
EOF
