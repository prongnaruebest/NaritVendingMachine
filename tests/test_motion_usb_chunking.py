from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from narit_vending.motion import (
    ActiveLimitError,
    AxisController,
    AxisMovePlan,
    ControlledStopError,
    NUCLEO_MOVE_CHUNK_STEPS,
    StopRequestedError,
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
            max_travel_mm=160.0,
            max_speed_mm_s=100.0,
            commissioned_max_speed_mm_s=100.0,
            max_pulse_hz=50_000.0,
            homing_timeout_s=30.0,
        )
        axis.direction = SimpleNamespace(value=False)
        axis.pulse = MagicMock()
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

    def test_successful_axis_move_runs_completion_verifier_once(self):
        axis = self.make_axis()
        axis.completion_verifier = MagicMock()
        axis.completion_verifier.begin.return_value = "pend-token"
        plan = AxisMovePlan("x", 0.0, 20.0, 20.0, 1, 4_000, 5.0, 4.0)

        axis._execute_plan(plan)

        axis.completion_verifier.begin.assert_called_once_with("x")
        axis.completion_verifier.verify.assert_called_once()
        self.assertEqual(axis.completion_verifier.verify.call_args.args[0], "pend-token")

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

    def test_max_limit_stop_preserves_home_and_allows_reverse_move(self):
        axis = self.make_axis(name="x", segment_limit=1_000_000)

        def max_limit_stop(**kwargs):
            axis.tail_limit.value = True
            self.assertTrue(kwargs["stop_requested"]())
            return {"steps": 31_500, "stopped": True}

        axis.motion_backend.move.side_effect = max_limit_stop
        plan = AxisMovePlan("x", 0.0, 160.0, 160.0, 1, 32_000, 5.0, 32.0)

        with self.assertRaises(ActiveLimitError):
            axis._execute_plan(plan)

        self.assertTrue(axis.is_homed)
        self.assertEqual(axis.position_steps, axis.mm_to_steps(axis.config.max_travel_mm))
        reverse = axis.plan_relative_move(-1.0, speed_mm_s=5.0)
        self.assertEqual(reverse.direction, axis.config.home_direction)

    def test_min_limit_stop_preserves_home_and_allows_forward_move(self):
        axis = self.make_axis(name="y", segment_limit=1_000_000)
        axis.position_steps = axis.mm_to_steps(axis.config.max_travel_mm)
        axis.head_limit.value = True

        with self.assertRaises(ActiveLimitError):
            axis._guard_during_move(axis.config.home_direction)

        self.assertTrue(axis.is_homed)
        self.assertEqual(axis.position_steps, 0)
        forward = axis.plan_relative_move(1.0, speed_mm_s=5.0)
        self.assertEqual(forward.direction, axis.config.forward_direction)

    def test_physical_limit_seek_ignores_software_travel_and_uses_sensor(self):
        axis = self.make_axis(name="z", segment_limit=1_000_000)
        axis.position_steps = axis.mm_to_steps(159.0)
        axis.is_homed = True

        def sensor_stopped_move(**kwargs):
            # Firmware frame extends far beyond the one millimetre remaining
            # in configured travel; only the physical sensor ends the seek.
            axis.tail_limit.value = True
            self.assertTrue(kwargs["stop_requested"]())
            return {"steps": 600, "stopped": True}

        axis.motion_backend.move.side_effect = sensor_stopped_move
        result = axis.seek_limit("max", speed_mm_s=2.0)

        self.assertEqual(result["sensor"], "triggered")
        self.assertTrue(result["software_travel_ignored"])
        self.assertEqual(result["steps"], 600)
        self.assertEqual(axis.position_steps, axis.mm_to_steps(160.0))
        self.assertTrue(axis.is_homed)

    def test_limit_seek_does_not_submit_another_frame_after_stop(self):
        axis = self.make_axis(name="x", segment_limit=1_000_000)

        def stopped_move(**kwargs):
            axis.controlled_stop_requested = lambda: True
            return {"steps": 250, "stopped": True}

        axis.motion_backend.move.side_effect = stopped_move

        with self.assertRaises(StopRequestedError):
            axis.seek_limit("max", speed_mm_s=5.0)

        self.assertEqual(axis.motion_backend.move.call_count, 1)


if __name__ == "__main__":
    unittest.main()
