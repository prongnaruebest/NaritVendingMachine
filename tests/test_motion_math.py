import math
import unittest

from narit_vending.domain.motion_math import (
    clamp_axis_speed_mm_s,
    effective_speed_limit_mm_s,
    mm_s_to_pulse_hz,
    pulse_hz_to_mm_s,
    pulse_hz_to_rpm,
    pulses_per_revolution,
)


class MotionMathTests(unittest.TestCase):
    def test_conversion_round_trip(self):
        pulses_per_rev = pulses_per_revolution(200, 10)
        self.assertEqual(pulses_per_rev, 2_000)
        self.assertAlmostEqual(pulse_hz_to_rpm(20_000, pulses_per_rev), 600.0)
        self.assertAlmostEqual(pulse_hz_to_mm_s(20_000, 200), 100.0)
        self.assertAlmostEqual(mm_s_to_pulse_hz(100, 200), 20_000.0)

    def test_effective_limit_uses_strictest_constraint(self):
        self.assertEqual(
            effective_speed_limit_mm_s(
                max_speed_mm_s=100,
                commissioned_max_speed_mm_s=80,
                max_pulse_hz=10_000,
                pulses_per_mm=200,
            ),
            50.0,
        )
        self.assertEqual(clamp_axis_speed_mm_s(75, speed_limit_mm_s=50), 50.0)

    def test_invalid_non_finite_or_non_positive_limits_are_rejected(self):
        invalid_values = (0, -1, math.nan, math.inf)
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    effective_speed_limit_mm_s(
                        max_speed_mm_s=value,
                        commissioned_max_speed_mm_s=5,
                        max_pulse_hz=1_000,
                        pulses_per_mm=200,
                    )

    def test_zero_rate_converts_to_zero(self):
        self.assertEqual(pulse_hz_to_rpm(0, 2_000), 0.0)
        self.assertEqual(pulse_hz_to_mm_s(0, 200), 0.0)
        self.assertEqual(mm_s_to_pulse_hz(0, 200), 0.0)


if __name__ == "__main__":
    unittest.main()
