"""Pure policies for directional limits and USB segment completion."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LimitViolation(str, Enum):
    MIN_ACTIVE = "MIN_ACTIVE"
    MAX_ACTIVE = "MAX_ACTIVE"
    SOFTWARE_TRAVEL = "SOFTWARE_TRAVEL"


class SegmentOutcome(str, Enum):
    COMPLETE = "COMPLETE"
    CONTROLLED_STOP = "CONTROLLED_STOP"
    MIN_LIMIT = "MIN_LIMIT"
    MAX_LIMIT = "MAX_LIMIT"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    STOP_REQUESTED = "STOP_REQUESTED"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class LimitAssessment:
    violation: LimitViolation | None
    target_steps: int


def active_physical_limit(
    *, direction: int, home_direction: int, min_active: bool, max_active: bool
) -> LimitViolation | None:
    """Return the physical end stop that blocks the requested direction."""

    if direction == home_direction and min_active:
        return LimitViolation.MIN_ACTIVE
    if direction != home_direction and max_active:
        return LimitViolation.MAX_ACTIVE
    return None


def assess_directional_limit(
    *,
    direction: int,
    home_direction: int,
    min_active: bool,
    max_active: bool,
    is_homed: bool,
    current_steps: int,
    delta_steps: int,
    max_steps: int,
) -> LimitAssessment:
    """Assess physical direction and, when homed, software travel."""

    target_steps = int(current_steps) + int(delta_steps)
    physical_violation = active_physical_limit(
        direction=direction,
        home_direction=home_direction,
        min_active=min_active,
        max_active=max_active,
    )
    if physical_violation is not None:
        return LimitAssessment(physical_violation, target_steps)
    if is_homed and (target_steps < 0 or target_steps > max_steps):
        return LimitAssessment(LimitViolation.SOFTWARE_TRAVEL, target_steps)
    return LimitAssessment(None, target_steps)


def classify_segment_outcome(
    *,
    expected_steps: int,
    completed_steps: int,
    stopped: bool,
    stop_reason: str,
    controlled_stop_active: bool = False,
) -> SegmentOutcome:
    """Classify a validated firmware segment result without side effects."""

    if completed_steps < 0 or completed_steps > expected_steps:
        raise ValueError("completed_steps must be within the submitted segment")
    if stopped and (stop_reason == "controlled jog release" or controlled_stop_active):
        return SegmentOutcome.CONTROLLED_STOP
    if stopped and stop_reason == "Min limit triggered":
        return SegmentOutcome.MIN_LIMIT
    if stopped and stop_reason == "Max limit triggered":
        return SegmentOutcome.MAX_LIMIT
    if stopped and stop_reason == "emergency stop":
        return SegmentOutcome.EMERGENCY_STOP
    if stopped and stop_reason == "stop requested":
        return SegmentOutcome.STOP_REQUESTED
    if completed_steps != expected_steps:
        return SegmentOutcome.INCOMPLETE
    return SegmentOutcome.COMPLETE
