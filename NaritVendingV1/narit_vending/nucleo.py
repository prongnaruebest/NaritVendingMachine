"""Fail-safe NUCLEO-F439ZI USB serial heartbeat backend."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable


class NucleoError(RuntimeError):
    """Raised when the Nucleo health link cannot complete a request."""


class NucleoLink:
    """Poll the Nucleo health protocol without exposing motion commands."""

    def __init__(self, config: dict[str, Any], serial_factory: Callable[..., Any] | None = None) -> None:
        self.port = str(config.get("port", "/dev/ttyACM0"))
        self.baudrate = int(config.get("baudrate", 115200))
        self.timeout_s = max(0.05, float(config.get("timeout_s", 0.5)))
        self.poll_interval_s = max(0.1, float(config.get("poll_interval_s", 0.5)))
        self.stale_after_s = max(self.poll_interval_s, float(config.get("stale_after_s", 1.5)))
        self.expected_device = str(config.get("expected_device", "NUCLEO-F439ZI"))
        self.expected_protocol = int(config.get("protocol_version", 1))
        self._serial_factory = serial_factory
        self._serial: Any | None = None
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._connected = False
        self._last_success_monotonic: float | None = None
        self._last_success_at: str | None = None
        self._last_error = "Nucleo has not completed its first heartbeat"
        self._last_payload: dict[str, Any] = {}

    @property
    def communication_ok(self) -> bool:
        with self._lock:
            return bool(
                self._connected
                and self._last_success_monotonic is not None
                and time.monotonic() - self._last_success_monotonic <= self.stale_after_s
            )

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._poll_once()
        self._thread = threading.Thread(target=self._poll_loop, name="nucleo-heartbeat", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self.poll_interval_s * 3))
        self._close_serial()

    def _open_serial(self) -> Any:
        if self._serial is not None:
            return self._serial
        factory = self._serial_factory
        if factory is None:
            try:
                import serial
            except ImportError as exc:
                raise NucleoError("pyserial is required for the Nucleo link") from exc
            factory = serial.Serial
        self._serial = factory(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout_s,
            write_timeout=self.timeout_s,
        )
        # Complete any partial line left by USB enumeration before the first PING.
        self._serial.write(b"\n")
        self._serial.flush()
        time.sleep(0.05)
        self._serial.reset_input_buffer()
        return self._serial

    def _close_serial(self) -> None:
        serial_port = self._serial
        self._serial = None
        if serial_port is not None:
            try:
                serial_port.close()
            except Exception:
                pass

    def _poll_loop(self) -> None:
        while not self._stop.wait(self.poll_interval_s):
            self._poll_once()

    def _poll_once(self) -> None:
        try:
            serial_port = self._open_serial()
            serial_port.write(b"PING\n")
            serial_port.flush()
            deadline = time.monotonic() + self.timeout_s
            payload: dict[str, Any] | None = None
            while time.monotonic() < deadline:
                raw = serial_port.readline()
                if not raw:
                    continue
                try:
                    candidate = json.loads(raw.decode("ascii"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if candidate.get("type") == "pong":
                    payload = candidate
                    break
            if payload is None:
                raise NucleoError("Nucleo heartbeat timed out")
            if payload.get("device") != self.expected_device:
                raise NucleoError(f"Unexpected Nucleo identity: {payload.get('device')!r}")
            if int(payload.get("protocol", -1)) != self.expected_protocol:
                raise NucleoError(f"Unsupported Nucleo protocol: {payload.get('protocol')!r}")
            if payload.get("safe") is not True:
                raise NucleoError("Nucleo did not report safe mode")
        except Exception as exc:
            self._close_serial()
            with self._lock:
                self._connected = False
                self._last_error = str(exc)
            return

        with self._lock:
            self._connected = True
            self._last_success_monotonic = time.monotonic()
            self._last_success_at = datetime.now(timezone.utc).isoformat()
            self._last_error = ""
            self._last_payload = dict(payload)

    def alarm_channel(self) -> dict[str, Any]:
        return {
            "code": "NUCLEO-COMM",
            "label": "Nucleo motion controller communication",
            "active": not self.communication_ok,
            "level": "fault",
            "detail": self._last_error or f"Connected to {self.port} at {self.baudrate} baud",
        }

    def status_payload(self) -> dict[str, Any]:
        with self._lock:
            payload = dict(self._last_payload)
            last_success_at = self._last_success_at
            last_error = self._last_error
        return {
            "enabled": True,
            "communication_ok": self.communication_ok,
            "transport": "usb_serial",
            "port": self.port,
            "baudrate": self.baudrate,
            "device": payload.get("device", self.expected_device),
            "protocol": payload.get("protocol", self.expected_protocol),
            "safe": payload.get("safe", False),
            "uptime_ms": payload.get("uptime_ms"),
            "last_success_at": last_success_at,
            "last_error": last_error,
        }
