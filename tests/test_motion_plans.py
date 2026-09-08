import unittest

from narit_vending.domain.motion_plans import AxisMovePlan, CoordinatedMovePlan, build_axis_move_plan


class MotionPlanTests(unittest.TestCase):
    def test_build_axis_move_plan_is_pure_and_directional(self):
        plan = build_axis_move_plan(
            axis="z",
            current_mm=10,
            distance_mm=-2.5,
            forward_direction=1,
            home_direction=0,
            pulses_per_mm=200,
            duration_s=0.5,
        )
        self.assertEqual(plan.target_mm, 7.5)
        self.assertEqual(plan.direction, 0)
        self.assertEqual(plan.steps, 500)
        self.assertEqual(plan.speed_mm_s, 5.0)

    def test_zero_distance_plan_never_requests_pulses(self):
        plan = build_axis_move_plan(
            axis="y",
            current_mm=12.25,
            distance_mm=0,
            forward_direction=1,
            home_direction=0,
            pulses_per_mm=80,
            duration_s=99,
        )
        self.assertEqual(plan.target_mm, 12.25)
        self.assertEqual(plan.steps, 0)
        self.assertEqual(plan.duration_s, 0)

    def test_axis_plan_is_immutable_and_serializable(self):
        plan = AxisMovePlan("x", 1.0, 11.0, 10.0, 1, 2_000, 5.0, 2.0)
        self.assertEqual(plan.pulse_hz, 1_000.0)
        self.assertEqual(plan.to_dict()["target_mm"], 11.0)
        with self.assertRaises(AttributeError):
            plan.steps = 1

    def test_coordinated_plan_ignores_stationary_axis_for_extrema(self):
        plan = CoordinatedMovePlan(
            axes={
                "x": AxisMovePlan("x", 0, 10, 10, 1, 2_000, 5, 2),
                "z": AxisMovePlan("z", 3, 3, 0, 1, 0, 0, 2),
            },
            duration_s=2,
            mode="speed",
        )
        self.assertEqual(plan.master_steps, 2_000)
        self.assertEqual(plan.total_distance_mm, 10)
        self.assertEqual(plan.to_dict()["axes"]["z"]["steps"], 0)


if __name__ == "__main__":
    unittest.main()
