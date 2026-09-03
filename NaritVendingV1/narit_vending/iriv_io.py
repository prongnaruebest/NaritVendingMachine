"""IRIV IO Modbus TCP backend.

The backend deliberately uses only the Python standard library so it can run
on the IRIV Pi without adding another deployment dependency.
"""

from __future__ import annotations

import socket
import struct
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable


class IRIVIOError(RuntimeError):
    """Raised when the IRIV IO module cannot complete a Modbus operation."""


class ModbusTCPClient:
    def __init__(self, host: str, port: int = 502, unit_id: int = 255, timeout_s: float = 0.5) -> None:
        self.host = host
        self.port = int(port)
        self.unit_id = int(unit_id)
        self.timeout_s = float(timeout_s)
        self._transaction_id = 0
        self._socket: socket.socket | None = None
        self._lock = threading.Lock()

    def close(self) -> None:
        with self._lock:
            self._close_unlocked()

    def _close_unlocked(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            finally:
                self._socket = None

    def _receive_exact(self, length: int) -> bytes:
        assert self._socket is not None
        result = bytearray()
        while len(result) < length:
            chunk = self._socket.recv(length - len(result))
            if not chunk:
                raise IRIVIOError("IRIV IO closed the Modbus TCP connection")
            result.extend(chunk)
        return bytes(result)

    def _exchange(self, pdu: bytes) -> bytes:
        with self._lock:
            self._transaction_id = (self._transaction_id + 1) & 0xFFFF
            tid = self._transaction_id
            request = struct.pack(">HHHB", tid, 0, len(pdu) + 1, self.unit_id) + pdu
            try:
                if self._socket is None:
                    self._socket = socket.create_connection((self.host, self.port), timeout=self.timeout_s)
                    self._socket.settimeout(self.timeout_s)
                self._socket.sendall(request)
                header = self._receive_exact(7)
                response_tid, protocol_id, length, unit_id = struct.unpack(">HHHB", header)
                if response_tid != tid or protocol_id != 0 or unit_id != self.unit_id or length < 2:
                    raise IRIVIOError("Invalid Modbus TCP response header")
                response = self._receive_exact(length - 1)
                if response[0] & 0x80:
                    code = response[1] if len(response) > 1 else -1
                    raise IRIVIOError(f"IRIV IO Modbus exception {code}")
                return response
            except (OSError, TimeoutError, IRIVIOError) as exc:
                self._close_unlocked()
                if isinstance(exc, IRIVIOError):
                    raise
                raise IRIVIOError(f"IRIV IO communication failed: {exc}") from exc

    def read_discrete_inputs(self, start: int, count: int) -> list[bool]:
        response = self._exchange(struct.pack(">BHH", 0x02, int(start), int(count)))
        if len(response) < 2 or response[0] != 0x02:
            raise IRIVIOError("Invalid read-discrete-inputs response")
        byte_count = response[1]
        if len(response) != byte_count + 2 or byte_count * 8 < count:
            raise IRIVIOError("Truncated read-discrete-inputs response")
        return [bool(response[2 + index // 8] & (1 << (index % 8))) for index in range(count)]

    def write_single_coil(self, address: int, value: bool) -> None:
        request = struct.pack(">BHH", 0x05, int(address), 0xFF00 if value else 0x0000)
        response = self._exchange(request)
        if response != request:
            raise IRIVIOError("Invalid write-single-coil response")


class IRIVInputDevice:
    def __init__(self, backend: "IRIVIOBackend", name: str) -> None:
        self._backend = backend
        self._name = name

    @property
    def value(self) -> bool:
        return self._backend.input_active(self._name)

    def close(self) -> None:
        return None


class IRIVOutputDevice:
    def __init__(self, backend: "IRIVIOBackend", name: str) -> None:
        self._backend = backend
        self._name = name

    @property
    def value(self) -> bool:
        return self._backend.output_value(self._name)

    def on(self) -> None:
        try:
            self._backend.set_output(self._name, True)
        except IRIVIOError:
            # State lamps must never prevent the controller process from
            # starting; motion/dispense commands enforce communication
            # separately and remain fail-safe.
            return None

    def off(self) -> None:
        try:
            self._backend.set_output(self._name, False)
        except IRIVIOError:
            return None

    def close(self) -> None:
        return None


class IRIVIOBackend:
    """Poll DI0-DI10 and provide fail-safe gpiozero-compatible adapters."""

    def __init__(self, config: dict[str, Any], client: ModbusTCPClient | None = None) -> None:
        self.config = config
        self.host = str(config.get("host", "10.0.0.10"))
        self.port = int(config.get("port", 502))
        self.unit_id = int(config.get("unit_id", 255))
        self.poll_interval_s = max(0.02, float(config.get("poll_interval_s", 0.1)))
        self.stale_after_s = max(self.poll_interval_s, float(config.get("stale_after_s", 0.5)))
        self.inputs = dict(config.get("inputs", {}))
        self.outputs = dict(config.get("outputs", {}))
        self._client = client or ModbusTCPClient(
            self.host, self.port, self.unit_id, float(config.get("timeout_s", 0.3))
        )
        self._lock = threading.RLock()
        self._raw_inputs = [False] * 11
        self._output_values = {name: False for name in self.outputs}
        self._connected = False
        self._outputs_initialized = False
        self._last_success_monotonic: float | None = None
        self._last_success_at: str | None = None
        self._last_error = "IRIV IO has not completed its first poll"
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

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
        self._thread = threading.Thread(target=self._poll_loop, name="iriv-io-poll", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self.poll_interval_s * 3))
        if self.communication_ok:
            for name in self.outputs:
                try:
                    self.set_output(name, False)
                except IRIVIOError:
                    break
        self._client.close()

    def _poll_loop(self) -> None:
        while not self._stop.wait(self.poll_interval_s):
            self._poll_once()

    def _poll_once(self) -> None:
        try:
            values = self._client.read_discrete_inputs(0, 11)
            if not self._outputs_initialized:
                for info in self.outputs.values():
                    safe_physical_value = False if bool(info.get("active_high", True)) else True
                    self._client.write_single_coil(0x0100 + int(info["channel"]), safe_physical_value)
        except IRIVIOError as exc:
            with self._lock:
                self._connected = False
                self._outputs_initialized = False
                self._last_error = str(exc)
            return
        now = time.monotonic()
        with self._lock:
            self._raw_inputs = values
            self._connected = True
            self._last_success_monotonic = now
            self._last_success_at = datetime.now(timezone.utc).isoformat()
            self._last_error = ""
            self._outputs_initialized = True

    def input_device(self, name: str) -> IRIVInputDevice:
        if name not in self.inputs:
            raise IRIVIOError(f"IRIV input '{name}' is not configured")
        return IRIVInputDevice(self, name)

    def output_device(self, name: str) -> IRIVOutputDevice:
        if name not in self.outputs:
            raise IRIVIOError(f"IRIV output '{name}' is not configured")
        return IRIVOutputDevice(self, name)

    def input_active(self, name: str) -> bool:
        info = self.inputs[name]
        # A safety input with unknown polarity must block operation until its
        # active state has been observed and commissioned at the cabinet.
        if (info.get("polarity_verified") is False) and bool(info.get("fail_safe", False)):
            return True
        if not self.communication_ok:
            return bool(info.get("fail_safe", False))
        channel = int(info["channel"])
        with self._lock:
            raw = self._raw_inputs[channel]
        return raw == bool(info.get("active_state", True))

    def output_value(self, name: str) -> bool:
        with self._lock:
            return bool(self._output_values.get(name, False))

    def set_output(self, name: str, value: bool) -> None:
        if name not in self.outputs:
            raise IRIVIOError(f"IRIV output '{name}' is not configured")
        if not self.communication_ok:
            raise IRIVIOError("IRIV IO is offline; output command rejected")
        info = self.outputs[name]
        logical_value = bool(value)
        with self._lock:
            if self._output_values.get(name) == logical_value:
                return
        physical_value = logical_value if bool(info.get("active_high", True)) else not logical_value
        try:
            self._client.write_single_coil(0x0100 + int(info["channel"]), physical_value)
        except IRIVIOError as exc:
            with self._lock:
                self._connected = False
                self._outputs_initialized = False
                self._last_error = str(exc)
            raise
        with self._lock:
            self._output_values[name] = logical_value

    def pulse_output(self, name: str, duration_s: float, stop_requested: Callable[[], bool] | None = None) -> None:
        self.set_output(name, True)
        try:
            deadline = time.monotonic() + max(0.01, duration_s)
            while time.monotonic() < deadline:
                if stop_requested and stop_requested():
                    raise IRIVIOError("Dispense output interrupted by stop request")
                if not self.communication_ok:
                    raise IRIVIOError("IRIV IO communication lost during dispense")
                time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
        finally:
            if self.communication_ok:
                self.set_output(name, False)

    def alarm_channels(self) -> list[dict[str, Any]]:
        channels = [{
            "code": "IO-COMM",
            "label": "IRIV IO communication",
            "active": not self.communication_ok,
            "level": "fault",
            "detail": self._last_error or f"Connected to {self.host}:{self.port}",
        }]
        mappings = (
            ("estop", "ESTOP-IO", "Emergency stop / safety relay"),
            ("door", "DOOR", "Door interlock"),
            ("x_alarm", "DRV-X", "X drive alarm"),
            ("y_alarm", "DRV-Y", "Y drive alarm"),
            ("z_alarm", "DRV-Z", "Z drive alarm"),
        )
        for name, code, label in mappings:
            if name in self.inputs:
                channels.append({"code": code, "label": label, "active": self.input_active(name), "level": "fault"})
        return channels

    def status_payload(self) -> dict[str, Any]:
        with self._lock:
            raw = list(self._raw_inputs)
            last_error = self._last_error
            last_success_at = self._last_success_at
            outputs = dict(self._output_values)
        return {
            "enabled": True,
            "communication_ok": self.communication_ok,
            "host": self.host,
            "port": self.port,
            "unit_id": self.unit_id,
            "last_success_at": last_success_at,
            "last_error": last_error,
            "raw_inputs": {f"DI{index}": value for index, value in enumerate(raw)},
            "inputs": {name: self.input_active(name) for name in self.inputs},
            "outputs": outputs,
        }
