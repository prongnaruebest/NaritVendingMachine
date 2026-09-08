"""Immutable motion plans shared by planning and hardware execution."""

from __future__ import annotations

from dataclasses import dataclass


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
