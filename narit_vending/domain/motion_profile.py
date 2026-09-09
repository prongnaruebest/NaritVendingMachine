"""Deterministic, hardware-neutral motion-profile primitives.

This module deliberately does not import GPIO, serial, Flask, or controller
code. The reference curve characterizes X/Y planning before firmware use.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable


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


@dataclass(frozen=True)
class ProfilePhase:
    name: str
    duration_s: float
    jerk_mm_s3: float

    def to_dict(self) -> dict[str, float | str]:
        return {
            "name": self.name,
            "duration_s": round(self.duration_s, 9),
            "jerk_mm_s3": round(self.jerk_mm_s3, 9),
        }


@dataclass(frozen=True)
class SevenSegmentSCurve:
    """Firmware-ready symmetric seven-phase, rest-to-rest S-curve."""

    distance_mm: float
    limits: MotionProfileLimits
    phases: tuple[ProfilePhase, ...]
    peak_velocity_mm_s: float
    peak_acceleration_mm_s2: float

    @property
    def duration_s(self) -> float:
        return sum(phase.duration_s for phase in self.phases)

    def sample(self, time_s: float) -> MotionProfileSample:
        if not math.isfinite(float(time_s)):
            raise ValueError("time_s must be finite")
        requested_time = min(max(float(time_s), 0.0), self.duration_s)
        elapsed = 0.0
        position = 0.0
        velocity = 0.0
        acceleration = 0.0
        active_jerk = 0.0
        for phase in self.phases:
            remaining = requested_time - elapsed
            if remaining <= 0:
                break
            dt = min(remaining, phase.duration_s)
            active_jerk = phase.jerk_mm_s3
            position += velocity * dt + 0.5 * acceleration * dt**2 + active_jerk * dt**3 / 6.0
            velocity += acceleration * dt + 0.5 * active_jerk * dt**2
            acceleration += active_jerk * dt
            elapsed += dt
            if dt < phase.duration_s:
                break
        if math.isclose(requested_time, self.duration_s, abs_tol=1e-12):
            return MotionProfileSample(requested_time, self.distance_mm, 0.0, 0.0, 0.0)
        return MotionProfileSample(requested_time, position, velocity, acceleration, active_jerk)

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_type": "seven_segment_s_curve",
            "distance_mm": round(self.distance_mm, 9),
            "duration_s": round(self.duration_s, 9),
            "peak_velocity_mm_s": round(self.peak_velocity_mm_s, 9),
            "peak_acceleration_mm_s2": round(self.peak_acceleration_mm_s2, 9),
            "phases": [phase.to_dict() for phase in self.phases],
        }


def _profile_phases(
    durations: Iterable[float], jerk: float, direction: float
) -> tuple[ProfilePhase, ...]:
    names = (
        "JERK_UP",
        "ACCEL_HOLD",
        "JERK_DOWN",
        "CRUISE",
        "DECEL_JERK_DOWN",
        "DECEL_HOLD",
        "DECEL_JERK_UP",
    )
    jerk_signs = (1.0, 0.0, -1.0, 0.0, -1.0, 0.0, 1.0)
    return tuple(
        ProfilePhase(name, max(float(duration), 0.0), direction * jerk * sign)
        for name, duration, sign in zip(names, durations, jerk_signs, strict=True)
    )


def build_seven_segment_scurve(
    distance_mm: float, limits: MotionProfileLimits
) -> SevenSegmentSCurve:
    """Build the time-optimal symmetric S-curve within V/A/J limits.

    The returned seven phases include zero-duration phases, producing a stable
    wire representation for short triangular, acceleration-limited, and cruise
    moves alike.
    """

    distance = float(distance_mm)
    if not math.isfinite(distance):
        raise ValueError("distance_mm must be finite")
    magnitude = abs(distance)
    if magnitude == 0:
        phases = _profile_phases((0.0,) * 7, limits.max_jerk_mm_s3, 1.0)
        return SevenSegmentSCurve(distance, limits, phases, 0.0, 0.0)

    velocity_limit = limits.max_velocity_mm_s
    acceleration_limit = limits.max_acceleration_mm_s2
    jerk_limit = limits.max_jerk_mm_s3
    direction = math.copysign(1.0, distance)

    jerk_time_at_acceleration_limit = acceleration_limit / jerk_limit
    velocity_at_acceleration_limit = acceleration_limit**2 / jerk_limit
    if velocity_limit <= velocity_at_acceleration_limit:
        jerk_time_for_velocity = math.sqrt(velocity_limit / jerk_limit)
        accel_hold_for_velocity = 0.0
    else:
        jerk_time_for_velocity = jerk_time_at_acceleration_limit
        accel_hold_for_velocity = velocity_limit / acceleration_limit - jerk_time_for_velocity

    no_cruise_distance = velocity_limit * (
        2.0 * jerk_time_for_velocity + accel_hold_for_velocity
    )
    if magnitude >= no_cruise_distance:
        jerk_time = jerk_time_for_velocity
        accel_hold = accel_hold_for_velocity
        cruise_time = (magnitude - no_cruise_distance) / velocity_limit
        peak_velocity = velocity_limit
        peak_acceleration = jerk_limit * jerk_time
    else:
        distance_to_reach_acceleration = (
            2.0 * acceleration_limit**3 / jerk_limit**2
        )
        if magnitude < distance_to_reach_acceleration:
            jerk_time = (magnitude / (2.0 * jerk_limit)) ** (1.0 / 3.0)
            accel_hold = 0.0
        else:
            jerk_time = jerk_time_at_acceleration_limit
            discriminant = jerk_time**2 + 4.0 * magnitude / acceleration_limit
            accel_hold = (-3.0 * jerk_time + math.sqrt(discriminant)) / 2.0
        cruise_time = 0.0
        peak_acceleration = jerk_limit * jerk_time
        peak_velocity = peak_acceleration * (jerk_time + accel_hold)

    phases = _profile_phases(
        (jerk_time, accel_hold, jerk_time, cruise_time, jerk_time, accel_hold, jerk_time),
        jerk_limit,
        direction,
    )
    return SevenSegmentSCurve(
        distance_mm=distance,
        limits=limits,
        phases=phases,
        peak_velocity_mm_s=peak_velocity,
        peak_acceleration_mm_s2=peak_acceleration,
    )
