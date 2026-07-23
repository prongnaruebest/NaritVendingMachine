"""MachineSnapshot — serialisable snapshot of the controller state.

This module has zero runtime dependencies outside the standard library so it
can be imported by both the controller process and the web process without
pulling in GPIO or Flask.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AxisSnapshot:
    """Immutable snapshot of a single axis."""

    name: str
    position_mm: float
    position_steps: int
    is_homed: bool
    head_limit: bool
    tail_limit: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AxisSnapshot":
        return cls(
            name=str(data["name"]),
            position_mm=float(data["position_mm"]),
            position_steps=int(data["position_steps"]),
            is_homed=bool(data["is_homed"]),
            head_limit=bool(data["head_limit"]),
            tail_limit=bool(data["tail_limit"]),
        )

    @classmethod
    def unknown(cls, name: str) -> "AxisSnapshot":
        return cls(name=name, position_mm=0.0, position_steps=0, is_homed=False, head_limit=False, tail_limit=False)


@dataclass(frozen=True)
class MachineSnapshot:
    """Immutable snapshot of the full machine state.

    Produced by the controller process and consumed by the web process.
    All fields must be JSON-serialisable primitives or collections thereof.
    """

    state: str  # "NOT_READY" | "HOMING" | "READY" | "MOVING" | "ALARM" | "E_STOP" | ...
    estop: bool
    axes: dict[str, AxisSnapshot]
    busy: bool
    active_command: str | None
    command_id: str | None
    command_started_at: str | None
    command_estimated_duration_s: float | None
    operation_phase: str
    operation_message: str
    operation_axis: str | None
    homing: dict[str, str]
    last_error: str
    alarm_channels: list[dict[str, Any]]
    config_revision: str
    motor_test_armed: bool
    configuration_restart_required: bool
    stop_requested: bool
    controlled_stop_requested: bool
    speed_override: float | None
    snapshot_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Flatten axes dict for backward-compatible /api/status shape
        for axis_name, axis_data in d["axes"].items():
            d[axis_name] = axis_data
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MachineSnapshot":
        axes_raw = data.get("axes", {})
        axes = {k: AxisSnapshot.from_dict(v) for k, v in axes_raw.items()}
        return cls(
            state=str(data.get("state", "UNKNOWN")),
            estop=bool(data.get("estop", False)),
            axes=axes,
            busy=bool(data.get("busy", False)),
            active_command=data.get("active_command"),
            command_id=data.get("command_id"),
            command_started_at=data.get("command_started_at"),
            command_estimated_duration_s=data.get("command_estimated_duration_s"),
            operation_phase=str(data.get("operation_phase", "ready")),
            operation_message=str(data.get("operation_message", "")),
            operation_axis=data.get("operation_axis"),
            homing=dict(data.get("homing", {})),
            last_error=str(data.get("last_error", "")),
            alarm_channels=list(data.get("alarm_channels", [])),
            config_revision=str(data.get("config_revision", "")),
            motor_test_armed=bool(data.get("motor_test_armed", False)),
            configuration_restart_required=bool(data.get("configuration_restart_required", False)),
            stop_requested=bool(data.get("stop_requested", False)),
            controlled_stop_requested=bool(data.get("controlled_stop_requested", False)),
            speed_override=data.get("speed_override"),
            snapshot_at=str(data.get("snapshot_at", _now_iso())),
        )

    @classmethod
    def offline(cls) -> "MachineSnapshot":
        """Return a sentinel snapshot indicating the controller is unreachable."""
        return cls(
            state="CONTROLLER_OFFLINE",
            estop=False,
            axes={name: AxisSnapshot.unknown(name) for name in ("x", "y", "z")},
            busy=False,
            active_command=None,
            command_id=None,
            command_started_at=None,
            command_estimated_duration_s=None,
            operation_phase="offline",
            operation_message="Controller process is unreachable",
            operation_axis=None,
            homing={"x": "unknown", "y": "unknown", "z": "unknown"},
            last_error="Controller IPC timeout",
            alarm_channels=[],
            config_revision="",
            motor_test_armed=False,
            configuration_restart_required=False,
            stop_requested=False,
            controlled_stop_requested=False,
            speed_override=None,
        )
