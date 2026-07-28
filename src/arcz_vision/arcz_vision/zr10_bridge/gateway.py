#!/usr/bin/env python3
"""Small same-origin gateway for the SIYI UI and MediaMTX WHEP signalling."""

from __future__ import annotations

import argparse
import http.client
import json
import mimetypes
import os
import posixpath
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from arcz_vision.zr10_bridge.siyi_protocol import SiyiController

HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
}


class GatewayHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ArczSiyiGateway/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.log_date_time_string()} {self.client_address[0]} {fmt % args}", flush=True)

    def do_GET(self) -> None:
        if self.path == "/ready":
            self._json(200, {"ready": True})
        elif self.path == "/api/health":
            self._health()
        elif self.path == "/api/control/status":
            self._json(200, self.server.controller.status())  # type: ignore[attr-defined]
        elif self.path == "/camera" or self.path.startswith("/camera/"):
            self._proxy()
        else:
            self._static()

    def do_HEAD(self) -> None:
        if self.path == "/ready":
            self._send(200, b"", "application/json")
        elif self.path == "/camera" or self.path.startswith("/camera/"):
            self._proxy()
        else:
            self._static(head_only=True)

    def do_POST(self) -> None:
        if self.path.startswith("/api/control/"):
            self._control()
        else:
            self._proxy_or_reject()

    def do_PATCH(self) -> None:
        self._proxy_or_reject()

    def do_DELETE(self) -> None:
        self._proxy_or_reject()

    def do_OPTIONS(self) -> None:
        self._proxy_or_reject()

    def _proxy_or_reject(self) -> None:
        if self.path == "/camera" or self.path.startswith("/camera/"):
            self._proxy()
        else:
            self._json(404, {"error": "not found"})

    def _proxy(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else None
        headers = {
            key: value for key, value in self.headers.items()
            if key.lower() not in HOP_HEADERS and key.lower() != "host"
        }
        headers["Host"] = "127.0.0.1:8889"
        connection = http.client.HTTPConnection("127.0.0.1", 8889, timeout=10)
        try:
            connection.request(self.command, self.path, body=body, headers=headers)
            response = connection.getresponse()
            payload = response.read()
            self.send_response(response.status, response.reason)
            for key, value in response.getheaders():
                lower = key.lower()
                if lower in HOP_HEADERS or lower == "content-length":
                    continue
                if lower == "location":
                    parsed = urlsplit(value)
                    value = parsed.path + (("?" + parsed.query) if parsed.query else "")
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)
        except (OSError, http.client.HTTPException) as exc:
            self._json(502, {"error": "media service unavailable", "detail": str(exc)})
        finally:
            connection.close()

    def _health(self) -> None:
        health_file: Path = self.server.health_file  # type: ignore[attr-defined]
        try:
            data = json.loads(health_file.read_text(encoding="utf-8"))
            age = max(0.0, time.time() - float(data.get("checked_at_epoch", 0)))
            data["check_age_s"] = round(age, 1)
            if age > 12:
                data["overall"] = "stale"
            self._json(200, data)
        except (OSError, ValueError, TypeError):
            self._json(200, {"overall": "starting", "check_age_s": None})

    def _control(self) -> None:
        if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
            self._json(415, {"error": "application/json required"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 1024:
                raise ValueError("invalid body length")
            body = json.loads(self.rfile.read(length))
            controller: SiyiController = self.server.controller  # type: ignore[attr-defined]
            if self.path == "/api/control/move":
                controller.move(int(body["pan"]), int(body["tilt"]))
            elif self.path == "/api/control/zoom":
                controller.zoom(int(body["direction"]))
            elif self.path == "/api/control/mode":
                controller.set_mode(str(body["mode"]).lower())
            elif self.path == "/api/control/center":
                controller.center()
            elif self.path == "/api/control/focus":
                controller.auto_focus()
            elif self.path == "/api/control/capture":
                action = str(body["action"]).lower()
                if action == "photo":
                    controller.take_photo()
                elif action == "start":
                    result = controller.set_recording(True)
                    self._json(200, {"ok": True, "result": result})
                    return
                elif action == "stop":
                    result = controller.set_recording(False)
                    self._json(200, {"ok": True, "result": result})
                    return
                else:
                    raise ValueError("capture action must be photo, start, or stop")
            else:
                self._json(404, {"error": "unknown control"})
                return
            self._json(200, {"ok": True})
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})
        except RuntimeError as exc:
            self._json(409, {"error": str(exc)})
        except OSError as exc:
            self._json(503, {"error": f"gimbal unavailable: {exc}"})

    def _static(self, head_only: bool = False) -> None:
        web_root: Path = self.server.web_root  # type: ignore[attr-defined]
        request_path = unquote(urlsplit(self.path).path)
        request_path = "index.html" if request_path == "/" else request_path.lstrip("/")
        clean = posixpath.normpath(request_path)
        target = (web_root / clean).resolve()
        if web_root not in target.parents and target != web_root:
            self._json(403, {"error": "forbidden"})
            return
        if not target.is_file():
            self._json(404, {"error": "not found"})
            return
        payload = target.read_bytes()
        media_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self._send(200, b"" if head_only else payload, media_type, content_length=len(payload))

    def _json(self, status: int, value: object) -> None:
        self._send(status, json.dumps(value, separators=(",", ":")).encode(), "application/json")

    def _send(self, status: int, payload: bytes, media_type: str, content_length: int | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(payload) if content_length is None else content_length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        if self.command != "HEAD" and payload:
            self.wfile.write(payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", action="append", dest="binds")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--web-root", type=Path, required=True)
    parser.add_argument("--health-file", type=Path, required=True)
    args = parser.parse_args()

    binds = args.binds or ["127.0.0.1"]
    controller = SiyiController()
    servers = []
    for bind in binds:
        server = ThreadingHTTPServer((bind, args.port), GatewayHandler)
        server.daemon_threads = True
        server.web_root = args.web_root.resolve()  # type: ignore[attr-defined]
        server.health_file = args.health_file.resolve()  # type: ignore[attr-defined]
        server.controller = controller  # type: ignore[attr-defined]
        servers.append(server)
        print(f"web gateway listening on http://{bind}:{args.port}", flush=True)
    for server in servers[1:]:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    servers[0].serve_forever()


if __name__ == "__main__":
    main()
