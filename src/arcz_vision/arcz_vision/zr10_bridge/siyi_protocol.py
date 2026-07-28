#!/usr/bin/env python3
"""Minimal, thread-safe SIYI gimbal SDK transport with motion dead-man stops."""

from __future__ import annotations

import binascii
import select
import socket
import struct
import threading
import time
from dataclasses import dataclass

START = b"\x55\x66"


def build_packet(sequence: int, command: int, payload: bytes = b"") -> bytes:
    """Build a SIYI SDK packet. CRC is CRC-16/XMODEM and is little-endian on wire."""
    header = START + b"\x01" + struct.pack("<HHB", len(payload), sequence & 0xFFFF, command)
    packet = header + payload
    return packet + struct.pack("<H", binascii.crc_hqx(packet, 0))


@dataclass(frozen=True)
class Packet:
    sequence: int
    command: int
    payload: bytes


def parse_packet(data: bytes) -> Packet | None:
    if len(data) < 10 or data[:2] != START:
        return None
    payload_length, sequence, command = struct.unpack_from("<HHB", data, 3)
    expected_length = 10 + payload_length
    if len(data) != expected_length:
        return None
    expected_crc = struct.unpack_from("<H", data, expected_length - 2)[0]
    if binascii.crc_hqx(data[:-2], 0) != expected_crc:
        return None
    return Packet(sequence, command, data[8:-2])


class SiyiController:
    CMD_AUTO_FOCUS = 0x04
    CMD_MANUAL_ZOOM = 0x05
    CMD_GIMBAL_ROTATION = 0x07
    CMD_CENTER = 0x08
    CMD_GIMBAL_STATUS = 0x0A
    CMD_FUNCTION = 0x0C

    MODES = {"lock": 3, "follow": 4, "fpv": 5}

    def __init__(self, host: str = "10.42.0.10", port: int = 37260) -> None:
        self.address = (host, port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.connect(self.address)
        self.socket.setblocking(False)
        self.lock = threading.Lock()
        self.sequence = 0
        self.last_receive_monotonic = 0.0
        self.last_command_ack: int | None = None
        self.last_motion_refresh = 0.0
        self.last_zoom_refresh = 0.0
        self.motion_active = False
        self.focus_due_monotonic = 0.0
        self.zoom_active = False
        self.selected_mode: str | None = None
        self.record_status: int | None = None
        self.running = True
        threading.Thread(target=self._worker, name="siyi-control", daemon=True).start()

    def _send(self, command: int, payload: bytes = b"") -> None:
        with self.lock:
            packet = build_packet(self.sequence, command, payload)
            self.sequence = (self.sequence + 1) & 0xFFFF
            self.socket.send(packet)

    def move(self, pan: int, tilt: int) -> None:
        pan = max(-100, min(100, int(pan)))
        tilt = max(-100, min(100, int(tilt)))
        was_active = self.motion_active
        self._send(self.CMD_GIMBAL_ROTATION, struct.pack("bb", pan, tilt))
        self.last_motion_refresh = time.monotonic()
        self.motion_active = pan != 0 or tilt != 0
        if self.motion_active:
            self.focus_due_monotonic = 0.0
        elif was_active:
            self.focus_due_monotonic = time.monotonic() + 0.35

    def zoom(self, direction: int) -> None:
        direction = max(-1, min(1, int(direction)))
        self._send(self.CMD_MANUAL_ZOOM, struct.pack("b", direction))
        self.last_zoom_refresh = time.monotonic()
        self.zoom_active = direction != 0

    def set_mode(self, mode: str) -> None:
        if mode not in self.MODES:
            raise ValueError("mode must be lock, follow, or fpv")
        self._send(self.CMD_FUNCTION, bytes((self.MODES[mode],)))
        self.selected_mode = mode

    def center(self) -> None:
        self._send(self.CMD_CENTER, b"\x01")

    def auto_focus(self) -> None:
        self._send(self.CMD_AUTO_FOCUS, b"\x01")
        self.focus_due_monotonic = 0.0

    def take_photo(self) -> None:
        self._send(self.CMD_FUNCTION, b"\x00")

    def set_recording(self, enabled: bool) -> str:
        status = self.record_status
        if status is None:
            raise RuntimeError("camera recording status is not available yet")
        if status == 2:
            raise RuntimeError("camera reports that no SD/TF card is inserted")
        currently_recording = status == 1
        if currently_recording == enabled:
            return "already_recording" if enabled else "already_stopped"
        self._send(self.CMD_FUNCTION, b"\x02")
        # Optimistic state prevents a double-click from sending the toggle twice.
        self.record_status = 1 if enabled else 0
        self._send(self.CMD_GIMBAL_STATUS)
        return "toggle_sent"

    def status(self) -> dict[str, object]:
        age = time.monotonic() - self.last_receive_monotonic
        return {
            "reachable": age < 5.0,
            "last_response_age_s": round(age, 1) if self.last_receive_monotonic else None,
            "last_ack_command": self.last_command_ack,
            "selected_mode": self.selected_mode,
            "recording": self.record_status == 1,
            "record_status": {0: "stopped", 1: "recording", 2: "no_card", 3: "data_loss"}.get(self.record_status, "unknown"),
        }

    def _stop_motion(self) -> None:
        # Repetition makes the safety-critical stop resilient to intermittent packet loss.
        for _ in range(3):
            self._send(self.CMD_GIMBAL_ROTATION, b"\x00\x00")
        self.motion_active = False
        self.focus_due_monotonic = time.monotonic() + 0.35

    def _stop_zoom(self) -> None:
        for _ in range(3):
            self._send(self.CMD_MANUAL_ZOOM, b"\x00")
        self.zoom_active = False

    def _enforce_deadman(self, now: float) -> None:
        if self.motion_active and now - self.last_motion_refresh > 0.30:
            self._stop_motion()
        if self.zoom_active and now - self.last_zoom_refresh > 0.45:
            self._stop_zoom()
        if self.focus_due_monotonic and now >= self.focus_due_monotonic and not self.motion_active:
            self.auto_focus()

    def _worker(self) -> None:
        next_status = 0.0
        while self.running:
            now = time.monotonic()
            self._enforce_deadman(now)
            if now >= next_status:
                self._send(self.CMD_GIMBAL_STATUS)
                next_status = now + 2.0
            readable, _, _ = select.select([self.socket], [], [], 0.05)
            if readable:
                try:
                    packet = parse_packet(self.socket.recv(2048))
                    if packet is not None:
                        self.last_receive_monotonic = time.monotonic()
                        self.last_command_ack = packet.command
                        if packet.command == self.CMD_GIMBAL_STATUS and len(packet.payload) >= 5:
                            self.record_status = packet.payload[3]
                            self.selected_mode = {0: "lock", 1: "follow", 2: "fpv"}.get(packet.payload[4], self.selected_mode)
                except BlockingIOError:
                    pass
