"""Local isolated digital I/O on the IRIV PiControl CM4."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any

from gpiozero import DigitalInputDevice, DigitalOutputDevice


class PiControlIOBackend:
    """Own PiControl DI0-DI3 and DO0-DO3 separately from Modbus IRIV I/O."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.inputs = dict(config.get("inputs", {}))
        self.outputs = dict(config.get("outputs", {}))
        self.poll_interval_s = max(0.01, float(config.get("poll_interval_s", 0.02)))
        self._devices: dict[str, DigitalInputDevice] = {}
        self._output_devices: dict[str, DigitalOutputDevice] = {}
        self._raw: dict[str, bool] = {}
        self._input_diagnostics: dict[str, dict[str, Any]] = {
            name: {
                "transitions": 0,
                "active_events": 0,
                "last_change_at": None,
                "active_since_at": None,
                "last_active_duration_ms": None,
                "_active_since_monotonic": None,
            }
            for name in self.inputs
        }
        self._error = ""
        self._last_success_at: str | None = None
        self._poll_latency_ms: float | None = None
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        for name, info in self.inputs.items():
            self._devices[name] = DigitalInputDevice(int(info["pin"]), pull_up=False)
        for name, info in self.outputs.items():
            self._output_devices[name] = DigitalOutputDevice(
                int(info["pin"]),
                active_high=bool(info.get("active_high", True)),
                initial_value=bool(info.get("initial_value", False)),
            )

    @property
    def communication_ok(self) -> bool:
        with self._lock:
            return not self._error and len(self._raw) == len(self.inputs)

    def start(self) -> None:
        self._poll_once()
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll_loop, name="picontrol-di-poll", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        for device in self._devices.values():
            device.close()
        for device in self._output_devices.values():
            device.off()
            device.close()

    def set_output(self, name: str, active: bool) -> None:
        if name not in self._output_devices:
            raise KeyError(f"PiControl output '{name}' is not configured")
        device = self._output_devices[name]
        device.on() if active else device.off()

    def output_active(self, name: str) -> bool:
        if name not in self._output_devices:
            return False
        return bool(self._output_devices[name].value)

    def _poll_loop(self) -> None:
        while not self._stop.wait(self.poll_interval_s):
            self._poll_once()

    def _poll_once(self) -> None:
        started = time.monotonic()
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            values = {name: bool(device.value) for name, device in self._devices.items()}
        except Exception as exc:
            with self._lock:
                self._error = str(exc)
            return
        with self._lock:
            for name, raw_value in values.items():
                previous = self._raw.get(name)
                if previous is None or previous == raw_value:
                    continue
                info = self.inputs[name]
                active_state = bool(info.get("active_state", True))
                diagnostic = self._input_diagnostics[name]
                diagnostic["transitions"] += 1
                diagnostic["last_change_at"] = now_iso
                if raw_value == active_state:
                    diagnostic["active_events"] += 1
                    diagnostic["active_since_at"] = now_iso
                    diagnostic["_active_since_monotonic"] = started
                elif previous == active_state:
                    active_since = diagnostic.get("_active_since_monotonic")
                    if active_since is not None:
                        diagnostic["last_active_duration_ms"] = round(
                            (started - float(active_since)) * 1000.0,
                            1,
                        )
                    diagnostic["active_since_at"] = None
                    diagnostic["_active_since_monotonic"] = None
            self._raw = values
            self._error = ""
            self._poll_latency_ms = round((time.monotonic() - started) * 1000.0, 3)
            self._last_success_at = datetime.now(timezone.utc).isoformat()

    def input_active(self, name: str) -> bool:
        info = self.inputs[name]
        if not self.communication_ok:
            return bool(info.get("fail_safe", False))
        with self._lock:
            raw = self._raw[name]
        return raw == bool(info.get("active_state", True))

    def alarm_channels(self) -> list[dict[str, Any]]:
        """Return only blocking communication/drive-alarm inputs.

        PEND is positive in-position feedback.  It intentionally remains in
        status_payload() and must never be promoted to a safety alarm merely
        because the signal is active.
        """
        result = [{
            "code": "PICTRL-DI",
            "label": "PiControl local digital inputs",
            "active": not self.communication_ok,
            "level": "fault",
            "detail": self._error or "GPIO input polling healthy",
        }]
        for name, code in (("x_alarm", "DRV-X"), ("y_alarm", "DRV-Y")):
            if name in self.inputs:
                result.append({
                    "code": code,
                    "label": str(self.inputs[name].get("label", name)),
                    "active": self.input_active(name),
                    "level": "fault",
                    "detail": f"PiControl DI{self.inputs[name].get('channel')} / GPIO{self.inputs[name].get('pin')}",
                })
        return result

    def position_channels(self) -> list[dict[str, Any]]:
        """Expose non-blocking HBS860H positioning-complete feedback."""
        result = []
        for name, code, axis in (("x_pend", "PEND-X", "x"), ("y_pend", "PEND-Y", "y")):
            if name in self.inputs:
                active = self.input_active(name)
                result.append({
                    "code": code,
                    "axis": axis,
                    "label": str(self.inputs[name].get("label", name)),
                    "active": active,
                    "state": "in_position" if active else "tracking",
                    "blocking": False,
                    "commissioned": bool(self.inputs[name].get("commissioned", False)),
                    "expected_active_state": bool(self.inputs[name].get("active_state", True)),
                    "settle_timeout_ms": int(self.inputs[name].get("settle_timeout_ms", 1000)),
                    "require_transition": bool(self.inputs[name].get("require_transition", False)),
                    **{
                        key: value
                        for key, value in self._input_diagnostics[name].items()
                        if not key.startswith("_")
                    },
                    "detail": f"PiControl DI{self.inputs[name].get('channel')} / GPIO{self.inputs[name].get('pin')}",
                })
        return result

    def status_payload(self) -> dict[str, Any]:
        with self._lock:
            raw = dict(self._raw)
            last_success_at = self._last_success_at
            poll_latency_ms = self._poll_latency_ms
            error = self._error
        input_details = {}
        for name, info in self.inputs.items():
            diagnostics = {
                key: value
                for key, value in self._input_diagnostics[name].items()
                if not key.startswith("_")
            }
            input_details[name] = {
                "channel": info.get("channel"),
                "pin": info.get("pin"),
                "label": info.get("label", name),
                "active_state": bool(info.get("active_state", True)),
                "fail_safe": bool(info.get("fail_safe", False)),
                "raw_channel": f"DI{info.get('channel')}",
                "raw_value": raw.get(name),
                "active": self.input_active(name),
                "kind": "position_feedback" if name.endswith("_pend") else "drive_alarm" if name.endswith("_alarm") else "digital_input",
                "safety_class": "advisory" if name.endswith("_pend") else "fault" if name.endswith("_alarm") else "process",
                "axis": name[0] if name[:2] in {"x_", "y_", "z_"} else None,
                "commissioned": bool(info.get("commissioned", False)),
                "settle_timeout_ms": int(info.get("settle_timeout_ms", 1000)),
                "require_transition": bool(info.get("require_transition", False)),
                **diagnostics,
            }
        return {
            "enabled": True,
            "communication_ok": self.communication_ok,
            "raw_inputs": {
                f"DI{info.get('channel')}": raw.get(name)
                for name, info in self.inputs.items()
            },
            "inputs": {name: self.input_active(name) for name in self.inputs},
            "position_channels": self.position_channels(),
            "outputs": {name: self.output_active(name) for name in self.outputs},
            "output_details": {
                name: {
                    "channel": info.get("channel"),
                    "pin": info.get("pin"),
                    "label": info.get("label", name),
                    "active_high": bool(info.get("active_high", True)),
                    "value": self.output_active(name),
                }
                for name, info in self.outputs.items()
            },
            "input_details": input_details,
            "last_success_at": last_success_at,
            "poll_latency_ms": poll_latency_ms,
            "poll_interval_s": self.poll_interval_s,
            "last_error": error,
        }
