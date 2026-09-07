from __future__ import annotations

import unittest

from narit_vending.motion import AxisConfig, MotionError


def axis_config(**overrides):
    values = dict(
        name="x", pulse_pin=1, direction_pin=2, head_limit_pin=3, tail_limit_pin=4,
        home_direction=0, forward_direction=1, steps_per_mm=200.0,
        max_travel_mm=220.0, max_speed_mm_s=250.0, default_speed_mm_s=5.0,
        motor_steps_per_rev=200, driver_microsteps=8, lead_screw_pitch_mm=8.0,
        max_pulse_hz=50_000.0, commissioned_max_speed_mm_s=100.0,
        homing_search_speed_mm_s=20.0, homing_latch_speed_mm_s=2.0,
        home_position_mm=10.0, homing_timeout_s=120.0,
    )
    values.update(overrides)
    return AxisConfig(**values)


class MotionV3RequirementTests(unittest.TestCase):
    def test_speed_conversions(self):
        cfg = axis_config()
        self.assertEqual(cfg.pulses_per_rev, 1600)
        self.assertAlmostEqual(cfg.pulse_hz_to_rpm(20_000), 750.0)
        self.assertAlmostEqual(cfg.pulse_hz_to_mm_s(20_000), 100.0)
        self.assertAlmostEqual(cfg.mm_s_to_pulse_hz(100.0), 20_000.0)

    def test_home_position_must_be_inside_travel(self):
        with self.assertRaises(MotionError):
            axis_config(home_position_mm=221.0)

    def test_commissioned_speed_cannot_exceed_pulse_limit(self):
        with self.assertRaises(MotionError):
            axis_config(max_pulse_hz=10_000.0, commissioned_max_speed_mm_s=100.0)

    def test_latch_speed_cannot_exceed_search_speed(self):
        with self.assertRaises(MotionError):
            axis_config(homing_search_speed_mm_s=2.0, homing_latch_speed_mm_s=3.0)

    def test_homing_search_can_exceed_normal_commissioned_speed(self):
        cfg = axis_config(
            commissioned_max_speed_mm_s=5.0,
            homing_search_speed_mm_s=20.0,
        )
        self.assertEqual(cfg.commissioned_max_speed_mm_s, 5.0)
        self.assertEqual(cfg.homing_search_speed_mm_s, 20.0)

    def test_homing_search_cannot_exceed_pulse_limit(self):
        with self.assertRaises(MotionError):
            axis_config(
                max_pulse_hz=2_000.0,
                commissioned_max_speed_mm_s=5.0,
                homing_search_speed_mm_s=20.0,
            )


if __name__ == "__main__":
    unittest.main()
