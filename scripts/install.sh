#!/usr/bin/env bash
# Fresh-host bootstrap. Run after checking out this repo and installing
# Docker, on a clean host (no leftover containers/services from a prior
# setup -- that's on the operator, not this script). Cleans up obsolete
# legacy systemd services from before this repo existed, checks
# dependencies, then brings the whole stack up with plain `docker compose
# up -d --build`. Docker's own `restart:
# unless-stopped` policy (plus `docker.service` being enabled at boot,
# which any Docker install already does) is what survives a reboot or a
# crashed container -- systemd is not used to wrap/supervise containers
# here, only for genuine host-level system tasks.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ${EUID} -ne 0 ]]; then
  exec sudo "$0" "$@"
fi

if [ ! -f "$REPO_ROOT/.env" ]; then
  cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
  chmod 600 "$REPO_ROOT/.env"
  if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
    chown "$SUDO_USER":"$(id -gn "$SUDO_USER")" "$REPO_ROOT/.env"
  fi
  cat <<EOF

The .env.example was copied to .env.

Now please go ahead and put your configuration into  $REPO_ROOT/.env

When you are done, come back and run this script agin.

EOF
  exit 0
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

echo "==> Ensuring the invoking user can run docker without sudo"
if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
  if id -nG "$SUDO_USER" 2>/dev/null | grep -qw docker; then
    echo "    $SUDO_USER is already in the docker group"
  else
    usermod -aG docker "$SUDO_USER"
    echo "    added $SUDO_USER to the docker group -- log out and back in" \
         "(or run 'newgrp docker') for this to take effect without sudo"
  fi
else
  echo "    skipped (no invoking sudo user detected)"
fi

echo "==> Ensuring the Docker daemon itself starts on boot (a real system task)"
systemctl enable docker >/dev/null 2>&1 || true

echo "==> Building the shared ROS2 base image"
docker build -t "arcz/ros2-base:${ROS_DISTRO}" \
  --build-arg "ROS_DISTRO=${ROS_DISTRO}" \
  "$REPO_ROOT/docker/base"

echo "==> Bringing the stack up"
(cd "$REPO_ROOT" && docker compose up -d --build)

echo
echo "Done."
echo
echo "Díky, že v tom lítáš s námi!"
echo
