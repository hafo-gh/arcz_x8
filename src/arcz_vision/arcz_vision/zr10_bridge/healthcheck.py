#!/usr/bin/env python3
"""One watchdog pass. Camera faults are reported; stuck local services are restarted."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import socket
import subprocess
import time
from pathlib import Path


def tcp_open(host: str, port: int, timeout: float = 0.7) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def http_json(port: int, path: str, timeout: float = 1.0) -> tuple[bool, dict]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        body = response.read()
        if response.status != 200:
            return False, {}
        return True, json.loads(body)
    except (OSError, ValueError, http.client.HTTPException):
        return False, {}
    finally:
        connection.close()


def load_previous(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    now = time.time()
    previous = load_previous(args.output)
    camera_reachable = tcp_open("10.42.0.10", 8554)
    api_ok, path_data = http_json(9997, "/v3/paths/get/camera")
    web_ok, _ = http_json(8080, "/ready")
    stream_ready = api_ok and bool(path_data.get("ready", False))
    tailscale_ready = tcp_open("100.99.9.62", 35465, timeout=0.3)

    api_failures = 0 if api_ok else int(previous.get("api_consecutive_failures", 0)) + 1
    web_failures = 0 if web_ok else int(previous.get("web_consecutive_failures", 0)) + 1
    last_restart = float(previous.get("last_restart_epoch", 0))
    action = "none"

    if api_failures >= 3 and now - last_restart >= 20:
        subprocess.run(["systemctl", "try-restart", "arcz-siyi-mediamtx.service"], check=False)
        last_restart = now
        action = "restarted mediamtx"
    if web_failures >= 3 and now - last_restart >= 20:
        subprocess.run(["systemctl", "try-restart", "arcz-siyi-web.service"], check=False)
        last_restart = now
        action = "restarted web gateway"

    if not api_ok or not web_ok:
        overall = "unhealthy"
    elif not camera_reachable or not stream_ready:
        overall = "degraded"
    elif not tailscale_ready:
        overall = "local-only"
    else:
        overall = "healthy"

    result = {
        "overall": overall,
        "checked_at_epoch": now,
        "camera_reachable": camera_reachable,
        "stream_ready": stream_ready,
        "mediamtx_api": api_ok,
        "web_gateway": web_ok,
        "tailscale": tailscale_ready,
        "readers": len(path_data.get("readers", [])) if api_ok else 0,
        "bytes_received": path_data.get("bytesReceived", 0) if api_ok else 0,
        "api_consecutive_failures": api_failures,
        "web_consecutive_failures": web_failures,
        "last_restart_epoch": last_restart,
        "watchdog_action": action,
    }
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, args.output)


if __name__ == "__main__":
    main()

