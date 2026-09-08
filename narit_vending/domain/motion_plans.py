"""Immutable motion plans shared by planning and hardware execution."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class AxisMovePlan:
    axis: str
    current_mm: float
    target_mm: float
    distance_mm: float
    direction: int
    steps: int
    speed_mm_s: float
    duration_s: float

    @property
    def pulse_hz(self) -> float:
        if self.duration_s <= 0:
            return 0.0
        return self.steps / self.duration_s

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "axis": self.axis,
            "current_mm": round(self.current_mm, 3),
            "target_mm": round(self.target_mm, 3),
            "distance_mm": round(self.distance_mm, 3),
            "direction": self.direction,
            "steps": self.steps,
            "speed_mm_s": round(self.speed_mm_s, 3),
            "duration_s": round(self.duration_s, 3),
            "pulse_hz": round(self.pulse_hz, 3),
        }


@dataclass(frozen=True)
class CoordinatedMovePlan:
    axes: dict[str, AxisMovePlan]
    duration_s: float
    mode: str

    @property
    def total_distance_mm(self) -> float:
        return max((abs(plan.distance_mm) for plan in self.axes.values()), default=0.0)

    @property
    def master_steps(self) -> int:
        return max((plan.steps for plan in self.axes.values()), default=0)

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "duration_s": round(self.duration_s, 3),
            "master_steps": self.master_steps,
            "total_distance_mm": round(self.total_distance_mm, 3),
            "axes": {name: plan.to_dict() for name, plan in self.axes.items()},
        }


def build_axis_move_plan(
    *,
    axis: str,
    current_mm: float,
    distance_mm: float,
    forward_direction: int,
    home_direction: int,
    pulses_per_mm: float,
    duration_s: float,
) -> AxisMovePlan:
    """Build an immutable axis plan from already-authorized inputs.

    Safety checks and target-boundary authorization intentionally happen before
    this function is called.  The function only performs deterministic plan
    construction and rejects malformed numeric input.
    """

    numeric_values = {
        "current_mm": current_mm,
        "distance_mm": distance_mm,
        "pulses_per_mm": pulses_per_mm,
        "duration_s": duration_s,
    }
    for name, value in numeric_values.items():
        if not math.isfinite(float(value)):
            raise ValueError(f"{name} must be finite")
    if pulses_per_mm <= 0:
        raise ValueError("pulses_per_mm must be greater than 0")
    if duration_s < 0:
        raise ValueError("duration_s cannot be negative")

    distance = float(distance_mm)
    current = float(current_mm)
    if distance == 0:
        return AxisMovePlan(axis, current, current, 0.0, forward_direction, 0, 0.0, 0.0)

    steps = abs(round(distance * pulses_per_mm))
    direction = forward_direction if distance > 0 else home_direction
    speed = 0.0 if duration_s == 0 else abs(distance) / duration_s
    return AxisMovePlan(
        axis=axis,
        current_mm=current,
        target_mm=current + distance,
        distance_mm=distance,
        direction=direction,
        steps=steps,
        speed_mm_s=speed,
        duration_s=float(duration_s),
    )
