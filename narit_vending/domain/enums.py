"""Canonical, dependency-neutral machine vocabulary."""

from enum import Enum, IntEnum


class AxisName(str, Enum):
    X = "x"
    Y = "y"
    Z = "z"


class Direction(IntEnum):
    REVERSE = 0
    FORWARD = 1


class CommandOutcome(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BUSY = "BUSY"


class AxisState(str, Enum):
    UNREFERENCED = "UNREFERENCED"
    IDLE = "IDLE"
    MOVING = "MOVING"
    HOMING_SEARCH = "HOMING_SEARCH"
    HOMING_BACKOFF = "HOMING_BACKOFF"
    HOMING_LATCH = "HOMING_LATCH"
    OFFSET_MOVE = "OFFSET_MOVE"
    AT_MIN = "AT_MIN"
    AT_MAX = "AT_MAX"
    POSITION_COMPLETE = "POSITION_COMPLETE"
    DRIVE_ALARM = "DRIVE_ALARM"
    FAILED = "FAILED"
