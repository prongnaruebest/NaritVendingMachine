import unittest

from narit_vending.domain.motion_plans import AxisMovePlan, CoordinatedMovePlan


class MotionPlanTests(unittest.TestCase):
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
