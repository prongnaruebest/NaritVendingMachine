"""Fail-safe NUCLEO-F439ZI USB serial heartbeat and motion backend."""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

from narit_vending.motion import MotionError, NucleoError

_log = logging.getLogger(__name__)

NUCLEO_MOTION_MIN_SPEED_HZ = 10.0
NUCLEO_MOTION_MAX_SPEED_HZ = 1000.0
NUCLEO_MOTION_MAX_STEPS = 10000


class NucleoLink:
    """Manage Nucleo USB serial communication and Protocol v2 motion generation."""

    def __init__(
        self,
        config: dict[str, Any],
        serial_factory: Callable[..., Any] | None = None,
        safety_permissive_fn: Callable[[], bool] | None = None,
    ) -> None:
        self.port = str(config.get("port", "/dev/ttyACM0"))
        self.baudrate = int(config.get("baudrate", 115200))
        self.timeout_s = max(0.05, float(config.get("timeout_s", 0.5)))
        self.poll_interval_s = max(0.05, float(config.get("poll_interval_s", 0.5)))
        self.stale_after_s = max(self.poll_interval_s, float(config.get("stale_after_s", 1.5)))
        self.expected_device = str(config.get("expected_device", "NUCLEO-F439ZI"))
        self.expected_protocol = int(config.get("protocol_version", 1))
        self._serial_factory = serial_factory
        self._safety_permissive_fn = safety_permissive_fn
        self._serial: Any | None = None
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._connected = False
        self._armed = False
        self._moving_axes: dict[str, int] = {"x": 0, "y": 0, "z": 0}
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

    @property
    def is_armed(self) -> bool:
        with self._lock:
            return self._armed

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
        try:
            self.disarm()
        except Exception:
            pass
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
        while not self._stop.is_set():
            interval = 0.15 if self._armed else self.poll_interval_s
            if self._stop.wait(interval):
                break
            self._poll_once()

    def _read_json_response(
        self,
        serial_port: Any,
        deadline: float,
        expected_types: set[str] | str | None = None,
    ) -> dict[str, Any] | None:
        if isinstance(expected_types, str):
            expected_types = {expected_types}

        while time.monotonic() < deadline:
            raw = serial_port.readline()
            if not raw:
                continue
            _log.debug("Nucleo RX raw: %r", raw)
            try:
                line_str = raw.decode("ascii", errors="replace").strip()
                if not line_str or not line_str.startswith("{"):
                    continue
                candidate = json.loads(line_str)
                if not isinstance(candidate, dict) or "type" not in candidate:
                    continue

                msg_type = candidate.get("type")

                # If Nucleo sent a boot announcement, track it but keep waiting for command response
                if msg_type == "boot":
                    _log.info("Nucleo booted: %r", candidate)
                    self._armed = False
                    self._moving_axes = {"x": 0, "y": 0, "z": 0}
                    continue

                # Update internal telemetry from any valid status message received
                if "device" in candidate:
                    self._last_payload = dict(candidate)
                    self._last_success_monotonic = time.monotonic()
                    self._last_success_at = datetime.now(timezone.utc).isoformat()
                    self._last_error = ""
                    self._connected = True
                if "armed" in candidate:
                    self._armed = bool(candidate["armed"])
                if "moving" in candidate and isinstance(candidate["moving"], dict):
                    self._moving_axes = {
                        k: int(candidate["moving"].get(k, 0)) for k in ("x", "y", "z")
                    }

                # Errors are always returned immediately
                if msg_type == "error":
                    return candidate

                # If specific types are expected, only return when matched
                if expected_types is not None:
                    if msg_type in expected_types:
                        return candidate
                    _log.debug("Skipping response type %r while expecting %r", msg_type, expected_types)
                    continue

                return candidate
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        return None

    def _poll_once(self) -> None:
        with self._lock:
            try:
                serial_port = self._open_serial()
                if self.expected_protocol >= 2 and self._armed:
                    permissive = True
                    if self._safety_permissive_fn is not None:
                        permissive = bool(self._safety_permissive_fn())
                    if not permissive:
                        # If safety interlock opened, disarm immediately
                        self._armed = False
                        try:
                            serial_port.reset_input_buffer()
                        except Exception:
                            pass
                        serial_port.write(b"DISARM\n")
                        serial_port.flush()
                        self._read_json_response(serial_port, time.monotonic() + self.timeout_s, expected_types={"ack"})
                        cmd = b"PING\n"
                        expected_types = {"pong"}
                    else:
                        cmd = b"HEARTBEAT SAFE\n"
                        expected_types = {"heartbeat"}
                else:
                    cmd = b"PING\n"
                    expected_types = {"pong"}

                try:
                    serial_port.reset_input_buffer()
                except Exception:
                    pass
                serial_port.write(cmd)
                serial_port.flush()
                deadline = time.monotonic() + self.timeout_s
                payload = self._read_json_response(serial_port, deadline, expected_types=expected_types)

                if payload is None:
                    raise NucleoError("Nucleo heartbeat timed out")
                if payload.get("device") != self.expected_device:
                    raise NucleoError(f"Unexpected Nucleo identity: {payload.get('device')!r}")
                if int(payload.get("protocol", -1)) != self.expected_protocol:
                    raise NucleoError(f"Unsupported Nucleo protocol: {payload.get('protocol')!r}")

                if self.expected_protocol == 1:
                    if payload.get("safe") is not True:
                        raise NucleoError("Nucleo did not report safe mode")
                else:
                    # Protocol 2+: track armed and moving states
                    if "armed" in payload:
                        self._armed = bool(payload["armed"])
                    if "moving" in payload and isinstance(payload["moving"], dict):
                        self._moving_axes = {
                            k: int(payload["moving"].get(k, 0)) for k in ("x", "y", "z")
                        }

            except Exception as exc:
                self._close_serial()
                self._connected = False
                self._last_error = str(exc)
                return

            self._connected = True
            self._last_success_monotonic = time.monotonic()
            self._last_success_at = datetime.now(timezone.utc).isoformat()
            self._last_error = ""
            self._last_payload = dict(payload)

    def arm(self, safety_permissive: bool = True) -> bool:
        """Arm Nucleo for motion output (Protocol 2+)."""
        if self.expected_protocol < 2:
            return True
        if not safety_permissive:
            self.disarm()
            return False

        with self._lock:
            try:
                serial_port = self._open_serial()
                try:
                    serial_port.reset_input_buffer()
                except Exception:
                    pass
                serial_port.write(b"ARM SAFE\n")
                serial_port.flush()
                deadline = time.monotonic() + self.timeout_s
                resp = self._read_json_response(serial_port, deadline, expected_types={"ack"})
                if resp and resp.get("type") == "ack" and resp.get("status") == "armed":
                    self._armed = True
                    self._last_success_monotonic = time.monotonic()
                    return True
                _log.warning("Nucleo arm rejected: %s", resp)
                return False
            except Exception as exc:
                self._last_error = f"Nucleo arm failed: {exc}"
                return False

    def disarm(self) -> bool:
        """Disarm Nucleo motion output."""
        with self._lock:
            self._armed = False
            try:
                serial_port = self._open_serial()
                try:
                    serial_port.reset_input_buffer()
                except Exception:
                    pass
                serial_port.write(b"DISARM\n")
                serial_port.flush()
                deadline = time.monotonic() + self.timeout_s
                self._read_json_response(serial_port, deadline, expected_types={"ack"})
                return True
            except Exception:
                return False

    def stop(self) -> bool:
        """Immediately stop all Nucleo pulse generation."""
        with self._lock:
            self._armed = False
            try:
                serial_port = self._open_serial()
                try:
                    serial_port.reset_input_buffer()
                except Exception:
                    pass
                serial_port.write(b"STOP\n")
                serial_port.flush()
                deadline = time.monotonic() + self.timeout_s
                self._read_json_response(serial_port, deadline, expected_types={"ack"})
                return True
            except Exception:
                return False

    def move(
        self,
        axis: str,
        direction: int,
        steps: int,
        speed_hz: float,
        timeout_s: float | None = None,
        stop_requested: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        """Execute a hardware pulse train via STM32 Nucleo Protocol v2."""
        axis_char = str(axis).upper()
        if axis_char not in ("X", "Y", "Z"):
            raise NucleoError(f"Invalid axis '{axis}' — expected X, Y, or Z")
        dir_val = 1 if int(direction) != 0 else 0
        steps_val = int(steps)
        if steps_val < 1 or steps_val > NUCLEO_MOTION_MAX_STEPS:
            raise NucleoError(f"steps must be between 1 and {NUCLEO_MOTION_MAX_STEPS} (requested {steps_val})")
        speed_val = float(speed_hz)
        if speed_val < NUCLEO_MOTION_MIN_SPEED_HZ or speed_val > NUCLEO_MOTION_MAX_SPEED_HZ:
            raise NucleoError(
                f"speed_hz must be between {NUCLEO_MOTION_MIN_SPEED_HZ:g} and {NUCLEO_MOTION_MAX_SPEED_HZ:g} Hz (requested {speed_val:g})"
            )

        with self._lock:
            if not self.communication_ok:
                raise NucleoError("Nucleo communication link is not online")

            if not self.arm(safety_permissive=True):
                raise NucleoError("Failed to arm Nucleo motion controller")

            serial_port = self._open_serial()
            try:
                serial_port.reset_input_buffer()
            except Exception:
                pass
            cmd = f"MOVE {axis_char} {dir_val} {steps_val} {int(round(speed_val))}\n"
            _log.info("Nucleo TX: %s", cmd.strip())
            serial_port.write(cmd.encode("ascii"))
            serial_port.flush()

            deadline = time.monotonic() + max(1.0, self.timeout_s)
            ack = self._read_json_response(serial_port, deadline, expected_types={"ack"})
            _log.info("Nucleo ACK: %r", ack)
            if not ack or ack.get("type") != "ack" or ack.get("status") != "moving":
                err = (ack or {}).get("error", "no ack")
                raise NucleoError(f"Move command rejected by Nucleo: {err}")

            # Keep watchdog alive with HEARTBEAT SAFE while waiting for completion
            estimated_duration_s = steps_val / speed_val
            overall_timeout_s = timeout_s or (estimated_duration_s + 4.0)
            overall_deadline = time.monotonic() + overall_timeout_s
            axis_key = axis_char.lower()

            try:
                while time.monotonic() < overall_deadline:
                    time.sleep(0.08)  # 80ms interval (watchdog is 500ms)

                    if stop_requested is not None and stop_requested():
                        self.stop()
                        raise NucleoError("Motion aborted by stop request or limit trigger")

                    serial_port.write(b"HEARTBEAT SAFE\n")
                    serial_port.flush()

                    hb = self._read_json_response(serial_port, time.monotonic() + 0.2, expected_types={"heartbeat"})
                    if hb:
                        self._last_success_monotonic = time.monotonic()
                        self._last_payload = dict(hb)
                        moving = hb.get("moving", {})
                        if isinstance(moving, dict) and moving.get(axis_key, 0) == 0:
                            # Axis finished moving
                            break
                else:
                    self.stop()
                    raise NucleoError(f"Move timed out after {overall_timeout_s:.1f} seconds")

            except Exception:
                self.stop()
                raise

        return {
            "ok": True,
            "axis": axis_key,
            "direction": dir_val,
            "steps": steps_val,
            "speed_hz": speed_val,
            "duration_s": estimated_duration_s,
        }

    def alarm_channel(self) -> dict[str, Any]:
        return {
            "code": "NUCLEO-COMM",
            "label": "Nucleo motion controller communication",
            "active": not self.communication_ok,
            "level": "fault",
            "detail": self._last_error or f"Connected to {self.port} at {self.baudrate} baud (v{self.expected_protocol})",
        }

    def status_payload(self) -> dict[str, Any]:
        with self._lock:
            payload = dict(self._last_payload)
            last_success_at = self._last_success_at
            last_error = self._last_error
            armed = self._armed
            moving = dict(self._moving_axes)
        return {
            "enabled": True,
            "communication_ok": self.communication_ok,
            "transport": "usb_serial",
            "port": self.port,
            "baudrate": self.baudrate,
            "device": payload.get("device", self.expected_device),
            "protocol": payload.get("protocol", self.expected_protocol),
            "safe": payload.get("safe", not armed),
            "armed": armed,
            "watchdog": payload.get("watchdog", False),
            "moving": moving,
            "uptime_ms": payload.get("uptime_ms"),
            "last_success_at": last_success_at,
            "last_error": last_error,
        }
