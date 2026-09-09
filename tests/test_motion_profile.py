from __future__ import annotations

import math

import pytest

from narit_vending.domain.motion_profile import MotionProfileLimits, build_quintic_scurve, supports_scurve


def test_scurve_scope_is_x_y_only():
    assert supports_scurve("x")
    assert supports_scurve("Y")
    assert not supports_scurve("z")


@pytest.mark.parametrize("invalid", [0.0, -1.0, math.nan, math.inf])
def test_limits_reject_invalid_values(invalid: float):
    with pytest.raises(ValueError):
        MotionProfileLimits(invalid, 20.0, 100.0)
    with pytest.raises(ValueError):
        MotionProfileLimits(30.0, invalid, 100.0)
    with pytest.raises(ValueError):
        MotionProfileLimits(30.0, 20.0, invalid)


def test_rest_to_rest_curve_is_continuous_and_reaches_exact_target():
    profile = build_quintic_scurve(100.0, MotionProfileLimits(30.0, 20.0, 100.0))
    start = profile.sample(0.0)
    end = profile.sample(profile.duration_s)
    assert (start.position_mm, start.velocity_mm_s, start.acceleration_mm_s2) == pytest.approx((0, 0, 0))
    assert (end.position_mm, end.velocity_mm_s, end.acceleration_mm_s2) == pytest.approx((100, 0, 0))


def test_curve_respects_all_limits():
    limits = MotionProfileLimits(30.0, 20.0, 100.0)
    profile = build_quintic_scurve(100.0, limits)
    assert profile.peak_velocity_mm_s <= limits.max_velocity_mm_s + 1e-9
    assert profile.peak_acceleration_mm_s2 <= limits.max_acceleration_mm_s2 + 1e-9
    assert profile.peak_jerk_mm_s3 <= limits.max_jerk_mm_s3 + 1e-9


def test_reverse_and_zero_distance_curves_are_deterministic():
    limits = MotionProfileLimits(30.0, 20.0, 100.0)
    reverse = build_quintic_scurve(-40.0, limits)
    assert reverse.sample(reverse.duration_s / 2).position_mm == pytest.approx(-20.0)
    assert reverse.sample(reverse.duration_s).position_mm == pytest.approx(-40.0)
    stationary = build_quintic_scurve(0.0, limits)
    assert stationary.duration_s == 0
    assert stationary.sample(123).position_mm == 0
