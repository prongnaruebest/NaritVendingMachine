"""Disabled-by-default transport adapter for buffered NUCLEO profiles.

The adapter is intentionally detached from :class:`NucleoLink`. Production
serial motion remains unchanged until firmware and integration gates pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from narit_vending.domain.errors import NucleoError
from narit_vending.domain.nucleo_profile_protocol import (
    BufferedProfileCommand,
    NucleoCapabilities,
    SensorTerminatedProfileCommand,
    validate_profile_sequence,
)


Exchange = Callable[[Mapping[str, object], float], Mapping[str, Any] | None]
WireExchange = Callable[[bytes, float], Mapping[str, Any] | None]


@dataclass(frozen=True)
class BufferedProfileTransportStatus:
    enabled: bool
    supported: bool
    staged_command_id: str | None
    staged_frames: int
    last_error: str


class BufferedProfileTransport:
    """Validate, stage, and start a profile through an injected exchange."""

    def __init__(
        self,
        *,
        exchange: Exchange,
        capabilities: NucleoCapabilities,
        enabled: bool = False,
        timeout_s: float = 0.5,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be greater than 0")
        self._exchange = exchange
        self._capabilities = capabilities
        self._enabled = bool(enabled)
        self._timeout_s = float(timeout_s)
        self._staged_command_id: str | None = None
        self._staged_frames = 0
        self._last_error = ""

    @property
    def status(self) -> BufferedProfileTransportStatus:
        return BufferedProfileTransportStatus(
            enabled=self._enabled,
            supported=self._capabilities.supports_buffered_scurve,
            staged_command_id=self._staged_command_id,
            staged_frames=self._staged_frames,
            last_error=self._last_error,
        )

    def _require_available(self) -> None:
        if not self._enabled:
            raise NucleoError("Buffered profile transport is disabled")
        if not self._capabilities.supports_buffered_scurve:
            raise NucleoError("NUCLEO handshake does not advertise buffered S-curve support")

    def _exchange_or_fail(self, payload: Mapping[str, object]) -> Mapping[str, Any]:
        response = self._exchange(payload, self._timeout_s)
        if response is None:
            raise NucleoError("Buffered profile transport timed out")
        if response.get("type") == "error":
            code = str(response.get("code", "firmware_error"))
            detail = str(response.get("error", response.get("detail", "profile rejected")))
            raise NucleoError(f"NUCLEO profile error {code}: {detail}")
        return response

    def stage(self, commands: Sequence[BufferedProfileCommand]) -> dict[str, object]:
        """Stage one ordered command without starting pulse generation."""

        self._require_available()
        sequence = validate_profile_sequence(commands)
        command_id = sequence[0].command_id
        self._staged_command_id = None
        self._staged_frames = 0
        self._last_error = ""
        try:
            for command in sequence:
                response = self._exchange_or_fail(command.payload())
                if response.get("type") != "ack":
                    raise NucleoError("NUCLEO did not acknowledge buffered profile frame")
                if response.get("command_id") != command_id:
                    raise NucleoError("NUCLEO profile ACK command_id mismatch")
                if response.get("sequence") != command.sequence:
                    raise NucleoError("NUCLEO profile ACK sequence mismatch")
                status = response.get("status")
                if status not in {"buffered", "duplicate"}:
                    raise NucleoError(f"Unexpected buffered profile ACK status: {status!r}")
                self._staged_frames += 1
            self._staged_command_id = command_id
            return {
                "ok": True,
                "command_id": command_id,
                "frames": self._staged_frames,
                "started": False,
            }
        except Exception as exc:
            self._staged_command_id = None
            self._staged_frames = 0
            self._last_error = str(exc)
            raise

    def start(self, command_id: str) -> dict[str, object]:
        """Start only the exact command which completed staging."""

        self._require_available()
        if not self._staged_command_id or self._staged_command_id != command_id:
            raise NucleoError("Profile start rejected because the command is not fully staged")
        try:
            response = self._exchange_or_fail(
                {"type": "profile_start", "command_id": command_id, "frames": self._staged_frames}
            )
            if response.get("type") != "ack" or response.get("command_id") != command_id:
                raise NucleoError("NUCLEO did not acknowledge profile start")
            if response.get("status") != "running":
                raise NucleoError(f"Unexpected profile start status: {response.get('status')!r}")
            return {"ok": True, "command_id": command_id, "status": "running"}
        except Exception as exc:
            self._last_error = str(exc)
            raise

    def accept_telemetry(self, payload: Mapping[str, Any]) -> dict[str, object]:
        """Validate asynchronous profile state without changing transport state."""

        command_id = payload.get("command_id")
        if command_id != self._staged_command_id:
            raise NucleoError("Profile telemetry command_id mismatch")
        state = str(payload.get("state", ""))
        if state == "BUFFER_UNDERRUN":
            self._last_error = "NUCLEO profile buffer underrun"
            raise NucleoError(self._last_error)
        allowed = {
            "BUFFERED",
            "ACCELERATING",
            "CRUISING",
            "DECELERATING",
            "CONTROLLED_STOP",
            "COMPLETE",
            "SAFETY_STOP",
            "FAILED",
        }
        if state not in allowed:
            raise NucleoError(f"Unknown profile telemetry state: {state!r}")
        return {"command_id": command_id, "state": state}


class SensorProfileWireTransport:
    """Detached ASCII transport candidate for sensor-terminated X/Y profiles."""

    def __init__(
        self,
        *,
        exchange: WireExchange,
        capabilities: NucleoCapabilities,
        enabled: bool = False,
        timeout_s: float = 0.5,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be greater than 0")
        self._exchange = exchange
        self._capabilities = capabilities
        self._enabled = bool(enabled)
        self._timeout_s = float(timeout_s)
        self._staged_command_id: str | None = None
        self._staged_frames = 0
        self._last_error = ""

    @property
    def status(self) -> BufferedProfileTransportStatus:
        return BufferedProfileTransportStatus(
            enabled=self._enabled,
            supported=self._capabilities.supports_sensor_terminated_scurve,
            staged_command_id=self._staged_command_id,
            staged_frames=self._staged_frames,
            last_error=self._last_error,
        )

    def _require_available(self) -> None:
        if not self._enabled:
            raise NucleoError("Sensor profile wire transport is disabled")
        if not self._capabilities.supports_sensor_terminated_scurve:
            raise NucleoError("NUCLEO handshake does not advertise sensor-terminated S-curve support")

    def _exchange_or_fail(self, line: str) -> Mapping[str, Any]:
        response = self._exchange((line + "\n").encode("ascii"), self._timeout_s)
        if response is None:
            raise NucleoError("Sensor profile wire transport timed out")
        if response.get("type") == "error":
            raise NucleoError(f"NUCLEO sensor profile error: {response.get('error', 'rejected')}")
        return response

    def stage(self, commands: Sequence[SensorTerminatedProfileCommand]) -> dict[str, object]:
        self._require_available()
        if not commands:
            raise NucleoError("Sensor profile sequence cannot be empty")
        profiles = validate_profile_sequence([command.profile for command in commands])
        command_id = profiles[0].command_id
        self._staged_command_id = None
        self._staged_frames = 0
        self._last_error = ""
        try:
            for command in commands:
                response = self._exchange_or_fail(command.wire_line())
                if response.get("type") != "ack":
                    raise NucleoError("NUCLEO did not acknowledge sensor profile frame")
                if response.get("command_id") != command_id:
                    raise NucleoError("NUCLEO sensor profile ACK command_id mismatch")
                if response.get("sequence") != command.profile.sequence:
                    raise NucleoError("NUCLEO sensor profile ACK sequence mismatch")
                if response.get("status") not in {"buffered", "duplicate"}:
                    raise NucleoError("Unexpected sensor profile ACK status")
                self._staged_frames += 1
            self._staged_command_id = command_id
            return {"ok": True, "command_id": command_id,
                    "frames": self._staged_frames, "started": False}
        except Exception as exc:
            self._staged_command_id = None
            self._staged_frames = 0
            self._last_error = str(exc)
            raise

    def start(self, command_id: str) -> dict[str, object]:
        self._require_available()
        if command_id != self._staged_command_id:
            raise NucleoError("Sensor profile start rejected because the command is not fully staged")
        try:
            response = self._exchange_or_fail(
                f"SENSOR_START {command_id} {self._staged_frames}"
            )
            if (response.get("type") != "ack" or
                    response.get("command_id") != command_id or
                    response.get("status") != "running"):
                raise NucleoError("NUCLEO did not acknowledge sensor profile start")
            return {"ok": True, "command_id": command_id, "status": "running"}
        except Exception as exc:
            self._last_error = str(exc)
            raise
