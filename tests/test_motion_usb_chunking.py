from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from narit_vending.motion import (
    AxisController,
    AxisMovePlan,
    ControlledStopError,
    NUCLEO_MOVE_CHUNK_STEPS,
)


class MotionUsbChunkingTests(unittest.TestCase):
    def make_axis(self, name="x", segment_limit=10_000):
        axis = AxisController.__new__(AxisController)
        axis.config = SimpleNamespace(
            name=name,
            steps_per_mm=200.0,
            default_speed_mm_s=5.0,
            forward_direction=1,
            home_direction=0,
            settle_delay=0.0,
        )
        axis.direction = SimpleNamespace(value=False)
        axis.estop = SimpleNamespace(value=False)
        axis.head_limit = SimpleNamespace(value=False)
        axis.tail_limit = SimpleNamespace(value=False)
        axis.stop_requested = lambda: False
        axis.controlled_stop_requested = lambda: False
        axis.position_steps = 0
        axis.is_homed = True
        axis.motion_backend = MagicMock(expected_protocol=3, max_move_steps=segment_limit)
        axis.motion_backend.move.side_effect = lambda **kwargs: {"steps": kwargs["steps"]}
        return axis

    def test_long_nucleo_move_is_split_into_safe_usb_segments(self):
        axis = self.make_axis()
        plan = AxisMovePlan("x", 0.0, 220.0, 220.0, 1, 44_000, 5.0, 44.0)

        moved = axis._execute_plan(plan)

        self.assertEqual(moved, 44_000)
        self.assertEqual(axis.position_steps, 44_000)
        self.assertEqual(
            [call.kwargs["steps"] for call in axis.motion_backend.move.call_args_list],
            [10_000, 10_000, 10_000, 10_000, 4_000],
        )
        self.assertTrue(all(
            call.kwargs["steps"] <= NUCLEO_MOVE_CHUNK_STEPS
            for call in axis.motion_backend.move.call_args_list
        ))

    def test_short_nucleo_move_remains_one_segment(self):
        axis = self.make_axis()
        plan = AxisMovePlan("x", 0.0, 20.0, 20.0, 1, 4_000, 5.0, 4.0)

        self.assertEqual(axis._execute_plan(plan), 4_000)
        self.assertEqual(axis.motion_backend.move.call_count, 1)
        self.assertEqual(axis.motion_backend.move.call_args.kwargs["steps"], 4_000)

    def test_segmentation_is_generic_for_every_axis_and_distance(self):
        for axis_name, total_steps, expected in (
            ("x", 10_001, [10_000, 1]),
            ("y", 52_345, [10_000, 10_000, 10_000, 10_000, 10_000, 2_345]),
            ("z", 80_000, [10_000] * 8),
        ):
            with self.subTest(axis=axis_name, total_steps=total_steps):
                axis = self.make_axis(name=axis_name)
                plan = AxisMovePlan(axis_name, 0.0, 1.0, 1.0, 1, total_steps, 5.0, total_steps / 1_000)
                self.assertEqual(axis._execute_plan(plan), total_steps)
                self.assertEqual(
                    [call.kwargs["steps"] for call in axis.motion_backend.move.call_args_list],
                    expected,
                )

    def test_backend_advertised_segment_limit_is_used_without_planner_change(self):
        axis = self.make_axis(segment_limit=25_000)
        plan = AxisMovePlan("x", 0.0, 1.0, 1.0, 1, 60_000, 5.0, 60.0)

        self.assertEqual(axis._execute_plan(plan), 60_000)
        self.assertEqual(
            [call.kwargs["steps"] for call in axis.motion_backend.move.call_args_list],
            [25_000, 25_000, 10_000],
        )

    def test_new_firmware_executes_full_axis_stroke_without_segment_pause(self):
        axis = self.make_axis(segment_limit=1_000_000)
        plan = AxisMovePlan("x", 0.0, 1600.0, 1600.0, 1, 110_000, 30.0, 1600.0 / 30.0)

        self.assertEqual(axis._execute_plan(plan), 110_000)
        self.assertEqual(axis.motion_backend.move.call_count, 1)
        self.assertEqual(axis.motion_backend.move.call_args.kwargs["steps"], 110_000)

    def test_hold_release_accounts_completed_steps_and_exits_as_controlled_stop(self):
        axis = self.make_axis(segment_limit=1_000_000)
        released = {"value": False}
        axis.controlled_stop_requested = lambda: released["value"]

        def stopped_move(**kwargs):
            released["value"] = True
            return {"steps": 1_234, "stopped": True}

        axis.motion_backend.move.side_effect = stopped_move
        plan = AxisMovePlan("x", 0.0, 1600.0, 1600.0, 1, 110_000, 30.0, 1600.0 / 30.0)

        with self.assertRaises(ControlledStopError):
            axis._execute_plan(plan)

        self.assertEqual(axis.motion_backend.move.call_count, 1)
        self.assertEqual(axis.position_steps, 1_234)

    def test_transient_hold_release_is_not_reported_as_incomplete_usb_move(self):
        axis = self.make_axis(name="z", segment_limit=1_000_000)
        released = {"value": False}
        axis.controlled_stop_requested = lambda: released["value"]

        def stopped_move(**kwargs):
            released["value"] = True
            self.assertTrue(kwargs["stop_requested"]())
            released["value"] = False
            return {"steps": 498, "stopped": True}

        axis.motion_backend.move.side_effect = stopped_move
        plan = AxisMovePlan("z", 0.0, 5.0, 5.0, 1, 1_000, 6.5, 5.0 / 6.5)

        with self.assertRaises(ControlledStopError):
            axis._execute_plan(plan)

        self.assertEqual(axis.position_steps, 498)


if __name__ == "__main__":
    unittest.main()
