import unittest

from narit_vending.motion import AxisConfig, MotionError, _build_half_periods


class MotionCharacterizationTests(unittest.TestCase):
    def test_2000_hz_profile_preserves_requested_pulse_count(self) -> None:
        pulse_count = 300
        duration_seconds = pulse_count / 2000.0

        half_periods = _build_half_periods(pulse_count, duration_seconds)

        self.assertEqual(len(half_periods), pulse_count)
        self.assertTrue(all(delay > 0 for delay in half_periods))

    def test_axis_rejects_equal_home_and_forward_direction(self) -> None:
        with self.assertRaises(MotionError):
            AxisConfig(
                name="x",
                pulse_pin=16,
                direction_pin=23,
                enable_pin=12,
                head_limit_pin=17,
                tail_limit_pin=27,
                home_direction=1,
                forward_direction=1,
                steps_per_mm=80.0,
                max_travel_mm=220.0,
            )


if __name__ == "__main__":
    unittest.main()
