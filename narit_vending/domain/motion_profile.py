"""Deterministic, hardware-neutral motion-profile primitives.

This module deliberately does not import GPIO, serial, Flask, or controller
code. The reference curve characterizes X/Y planning before firmware use.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


SMOOTHED_AXES = frozenset({"x", "y"})
_PEAK_NORMALIZED_VELOCITY = 1.875
_PEAK_NORMALIZED_ACCELERATION = 10.0 / math.sqrt(3.0)
_PEAK_NORMALIZED_JERK = 60.0


def supports_scurve(axis: str) -> bool:
    """Return whether the approved scope allows S-curve work for *axis*."""

    return str(axis).strip().lower() in SMOOTHED_AXES


@dataclass(frozen=True)
class MotionProfileLimits:
    max_velocity_mm_s: float
    max_acceleration_mm_s2: float
    max_jerk_mm_s3: float

    def __post_init__(self) -> None:
        values = (
            ("max_velocity_mm_s", self.max_velocity_mm_s),
            ("max_acceleration_mm_s2", self.max_acceleration_mm_s2),
            ("max_jerk_mm_s3", self.max_jerk_mm_s3),
        )
        for name, value in values:
            if not math.isfinite(float(value)) or value <= 0:
                raise ValueError(f"{name} must be a finite number greater than 0")


@dataclass(frozen=True)
class MotionProfileSample:
    time_s: float
    position_mm: float
    velocity_mm_s: float
    acceleration_mm_s2: float
    jerk_mm_s3: float


@dataclass(frozen=True)
class QuinticSCurve:
    """Symmetric rest-to-rest S-curve with analytically bounded derivatives."""

    distance_mm: float
    duration_s: float
    limits: MotionProfileLimits

    def sample(self, time_s: float) -> MotionProfileSample:
        if not math.isfinite(float(time_s)):
            raise ValueError("time_s must be finite")
        clamped_time = min(max(float(time_s), 0.0), self.duration_s)
        if self.duration_s == 0:
            return MotionProfileSample(0.0, 0.0, 0.0, 0.0, 0.0)

        u = clamped_time / self.duration_s
        position_scale = (10 * u**3) - (15 * u**4) + (6 * u**5)
        velocity_scale = (30 * u**2) - (60 * u**3) + (30 * u**4)
        acceleration_scale = (60 * u) - (180 * u**2) + (120 * u**3)
        jerk_scale = 60 - (360 * u) + (360 * u**2)
        return MotionProfileSample(
            time_s=clamped_time,
            position_mm=self.distance_mm * position_scale,
            velocity_mm_s=(self.distance_mm / self.duration_s) * velocity_scale,
            acceleration_mm_s2=(self.distance_mm / self.duration_s**2) * acceleration_scale,
            jerk_mm_s3=(self.distance_mm / self.duration_s**3) * jerk_scale,
        )

    @property
    def peak_velocity_mm_s(self) -> float:
        return 0.0 if self.duration_s == 0 else abs(self.distance_mm) * _PEAK_NORMALIZED_VELOCITY / self.duration_s

    @property
    def peak_acceleration_mm_s2(self) -> float:
        return 0.0 if self.duration_s == 0 else abs(self.distance_mm) * _PEAK_NORMALIZED_ACCELERATION / self.duration_s**2

    @property
    def peak_jerk_mm_s3(self) -> float:
        return 0.0 if self.duration_s == 0 else abs(self.distance_mm) * _PEAK_NORMALIZED_JERK / self.duration_s**3


def build_quintic_scurve(distance_mm: float, limits: MotionProfileLimits) -> QuinticSCurve:
    """Build the shortest normalized curve satisfying all configured limits."""

    distance = float(distance_mm)
    if not math.isfinite(distance):
        raise ValueError("distance_mm must be finite")
    magnitude = abs(distance)
    if magnitude == 0:
        return QuinticSCurve(distance, 0.0, limits)

    velocity_duration = magnitude * _PEAK_NORMALIZED_VELOCITY / limits.max_velocity_mm_s
    acceleration_duration = math.sqrt(
        magnitude * _PEAK_NORMALIZED_ACCELERATION / limits.max_acceleration_mm_s2
    )
    jerk_duration = (magnitude * _PEAK_NORMALIZED_JERK / limits.max_jerk_mm_s3) ** (1.0 / 3.0)
    return QuinticSCurve(distance, max(velocity_duration, acceleration_duration, jerk_duration), limits)
