# arcz/x8

ROS2 (Jazzy) software for the `arcz` drone companion computer. Each package
under `src/` builds and runs as its own Docker container:

- **arcz_connection** — MAVLink bridge to the flight controller, Zenoh DDS
  router, internet connectivity monitoring.
- **arcz_observability** — MCAP recording of all ROS topics while armed,
  Foxglove bridge for live introspection.
- **arcz_postflight** — collects the PX4 ULog and mcap recording after each
  qualifying flight and uploads them to a remote server.

See [`docs/ros2.md`](docs/ros2.md) for the full node/topic reference.

## Install on the companion computer

Requires Docker + the `docker compose` plugin already installed.

```bash
git clone https://github.com/hafo-gh/arcz_x8.git
cd arcz_x8
sudo ./scripts/install.sh
```

On first run it copies `.env.example` to `.env` and stops so you can fill in
this vehicle's configuration (FC serial device, vehicle UUID, upload server,
upload token). Edit `.env`, then run `sudo ./scripts/install.sh` again to
build the images and bring everything up.

Re-running the script later is safe — it rebuilds and restarts the stack
with whatever is currently in `.env`.
