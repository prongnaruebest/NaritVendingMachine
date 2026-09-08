"""Dependency-neutral machine domain vocabulary.

This package must remain free of Flask, GPIO, serial, Modbus and persistence
imports so the same rules can be exercised deterministically in tests.
"""

from .errors import (
    ActiveLimitError,
    ControlledStopError,
    EmergencyStopError,
    LimitTriggeredError,
    MotionError,
    NotHomedError,
    NucleoError,
    StopRequestedError,
    TravelBoundaryError,
)
from .enums import AxisName, AxisState, CommandOutcome, Direction, MachineState
from .machine_state import normalize_machine_state
from .safety import AxisSafetySnapshot, SafetyReasonCode, SafetySnapshot

__all__ = [
    "ActiveLimitError",
    "ControlledStopError",
    "EmergencyStopError",
    "LimitTriggeredError",
    "MotionError",
    "NotHomedError",
    "NucleoError",
    "StopRequestedError",
    "TravelBoundaryError",
    "AxisName",
    "AxisState",
    "CommandOutcome",
    "Direction",
    "AxisSafetySnapshot",
    "SafetyReasonCode",
    "SafetySnapshot",
    "MachineState",
    "normalize_machine_state",
]
