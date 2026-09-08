"""Dependency-neutral safety decision vocabulary and immutable inputs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class SafetyReasonCode(str, Enum):
    DEMO_ACTIVE = "DEMO_ACTIVE"
    ESTOP_ACTIVE = "ESTOP_ACTIVE"
    STOP_LATCH_ACTIVE = "STOP_LATCH_ACTIVE"
    CONFIG_RESTART_REQUIRED = "CONFIG_RESTART_REQUIRED"
    MACHINE_BUSY = "MACHINE_BUSY"
    MOTOR_TEST_ARMED = "MOTOR_TEST_ARMED"
    MOTOR_TEST_NOT_ARMED = "MOTOR_TEST_NOT_ARMED"
    STATE_ESTOP = "STATE_ESTOP"
    STATE_ALARM = "STATE_ALARM"
    STATE_HOMING = "STATE_HOMING"


def axis_not_homed_code(axis: str) -> str:
    return f"AXIS_{axis.upper()}_NOT_HOMED"


def limit_conflict_code(axis: str) -> str:
    return f"LIMIT_CONFLICT_{axis.upper()}"


@dataclass(frozen=True)
class AxisSafetySnapshot:
    is_homed: bool
    min_limit: bool
    max_limit: bool


@dataclass(frozen=True)
class SafetySnapshot:
    """The minimum authoritative state consumed by the safety policy."""

    state: str
    estop: bool
    busy: bool
    stop_requested: bool
    configuration_restart_required: bool
    motor_test_armed: bool
    axes: Mapping[str, AxisSafetySnapshot]
    demo_state: str = ""

    @classmethod
    def from_machine_snapshot(cls, snapshot: Any) -> "SafetySnapshot":
        return cls(
            state=str(snapshot.state),
            estop=bool(snapshot.estop),
            busy=bool(snapshot.busy),
            stop_requested=bool(snapshot.stop_requested),
            configuration_restart_required=bool(snapshot.configuration_restart_required),
            motor_test_armed=bool(snapshot.motor_test_armed),
            axes=MappingProxyType(
                {
                    name: AxisSafetySnapshot(
                        is_homed=bool(axis.is_homed),
                        min_limit=bool(axis.head_limit),
                        max_limit=bool(axis.tail_limit),
                    )
                    for name, axis in snapshot.axes.items()
                }
            ),
            demo_state=str(snapshot.demo_status.get("state", "")).upper(),
        )
