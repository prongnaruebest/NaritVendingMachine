"""Pure motion conversion and speed-limit calculations.

This module deliberately has no GPIO, transport, controller, or configuration
loading dependencies.  Hardware-facing code may consume these calculations,
but safety authorization remains the controller's responsibility.
"""

from __future__ import annotations

import math


def _positive_finite(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{name} must be a finite number greater than 0")
    return result


def pulses_per_revolution(motor_steps_per_rev: float, driver_microsteps: float) -> float:
    """Return commanded input pulses for one motor revolution."""

    return _positive_finite(motor_steps_per_rev, "motor_steps_per_rev") * _positive_finite(
        driver_microsteps, "driver_microsteps"
    )


def pulse_hz_to_rpm(pulse_hz: float, pulses_per_rev: float) -> float:
    pulse_rate = float(pulse_hz)
    if not math.isfinite(pulse_rate) or pulse_rate < 0:
        raise ValueError("pulse_hz must be a finite number greater than or equal to 0")
    return pulse_rate * 60.0 / _positive_finite(pulses_per_rev, "pulses_per_rev")


def pulse_hz_to_mm_s(pulse_hz: float, pulses_per_mm: float) -> float:
    pulse_rate = float(pulse_hz)
    if not math.isfinite(pulse_rate) or pulse_rate < 0:
        raise ValueError("pulse_hz must be a finite number greater than or equal to 0")
    return pulse_rate / _positive_finite(pulses_per_mm, "pulses_per_mm")


def mm_s_to_pulse_hz(speed_mm_s: float, pulses_per_mm: float) -> float:
    speed = float(speed_mm_s)
    if not math.isfinite(speed) or speed < 0:
        raise ValueError("speed_mm_s must be a finite number greater than or equal to 0")
    return speed * _positive_finite(pulses_per_mm, "pulses_per_mm")


def effective_speed_limit_mm_s(
    *,
    max_speed_mm_s: float,
    commissioned_max_speed_mm_s: float,
    max_pulse_hz: float,
    pulses_per_mm: float,
) -> float:
    """Return the strictest commissioned, mechanical, or pulse-rate limit."""

    return min(
        _positive_finite(max_speed_mm_s, "max_speed_mm_s"),
        _positive_finite(commissioned_max_speed_mm_s, "commissioned_max_speed_mm_s"),
        _positive_finite(max_pulse_hz, "max_pulse_hz")
        / _positive_finite(pulses_per_mm, "pulses_per_mm"),
    )


def clamp_axis_speed_mm_s(requested_speed_mm_s: float, *, speed_limit_mm_s: float) -> float:
    requested = _positive_finite(requested_speed_mm_s, "speed_mm_s")
    return min(requested, _positive_finite(speed_limit_mm_s, "speed_limit_mm_s"))
