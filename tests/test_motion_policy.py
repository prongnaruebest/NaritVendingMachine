import unittest

from narit_vending.domain.motion_policy import (
    LimitViolation,
    SegmentOutcome,
    active_physical_limit,
    assess_directional_limit,
    classify_segment_outcome,
)


class MotionPolicyTests(unittest.TestCase):
    def test_physical_limit_policy_is_directional(self):
        self.assertIs(
            active_physical_limit(direction=0, home_direction=0, min_active=True, max_active=False),
            LimitViolation.MIN_ACTIVE,
        )
        self.assertIsNone(
            active_physical_limit(direction=1, home_direction=0, min_active=True, max_active=False)
        )

    def test_active_limit_blocks_only_direction_into_sensor(self):
        into_min = assess_directional_limit(
            direction=0, home_direction=0, min_active=True, max_active=False,
            is_homed=True, current_steps=0, delta_steps=-80, max_steps=136_000,
        )
        away_from_min = assess_directional_limit(
            direction=1, home_direction=0, min_active=True, max_active=False,
            is_homed=True, current_steps=0, delta_steps=80, max_steps=136_000,
        )
        self.assertIs(into_min.violation, LimitViolation.MIN_ACTIVE)
        self.assertIsNone(away_from_min.violation)

    def test_software_travel_applies_only_after_homing(self):
        homed = assess_directional_limit(
            direction=1, home_direction=0, min_active=False, max_active=False,
            is_homed=True, current_steps=100, delta_steps=901, max_steps=1_000,
        )
        unhomed = assess_directional_limit(
            direction=1, home_direction=0, min_active=False, max_active=False,
            is_homed=False, current_steps=100, delta_steps=901, max_steps=1_000,
        )
        self.assertIs(homed.violation, LimitViolation.SOFTWARE_TRAVEL)
        self.assertIsNone(unhomed.violation)

    def test_segment_outcome_priority_preserves_controlled_release(self):
        result = classify_segment_outcome(
            expected_steps=1_000, completed_steps=498, stopped=True,
            stop_reason="", controlled_stop_active=True,
        )
        self.assertIs(result, SegmentOutcome.CONTROLLED_STOP)

    def test_limit_and_incomplete_segment_are_distinct(self):
        limit = classify_segment_outcome(
            expected_steps=1_000, completed_steps=600, stopped=True,
            stop_reason="Max limit triggered",
        )
        incomplete = classify_segment_outcome(
            expected_steps=1_000, completed_steps=600, stopped=False, stop_reason="",
        )
        self.assertIs(limit, SegmentOutcome.MAX_LIMIT)
        self.assertIs(incomplete, SegmentOutcome.INCOMPLETE)

    def test_invalid_completed_count_is_rejected(self):
        with self.assertRaises(ValueError):
            classify_segment_outcome(
                expected_steps=100, completed_steps=101, stopped=False, stop_reason="",
            )


if __name__ == "__main__":
    unittest.main()
