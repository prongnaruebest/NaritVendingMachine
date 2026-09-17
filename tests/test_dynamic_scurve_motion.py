from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from narit_vending.domain.errors import LimitTriggeredError
from narit_vending.domain.motion_plans import AxisMovePlan, CoordinatedMovePlan
from narit_vending.domain.nucleo_profile_protocol import (
    DynamicAxisConfigCommand,
    DynamicPositionCommand,
    DynamicStartCommand,
    DynamicTargetCommand,
)
from narit_vending.motion import MotionController


class MockBackend:
    def __init__(self) -> None:
        self.expected_protocol = 4
        self.supports_buffered_scurve = True
        self.configured_axes: list[DynamicAxisConfigCommand] = []
        self.positions: list[DynamicPositionCommand] = []
        self.staged_targets: list[DynamicTargetCommand] = []
        self.started_motions: list[DynamicStartCommand] = []
        self.mock_start_result = {"status": "ok", "stopped": False}
        self.is_armed = False

    def arm(self, safety_permissive: bool = True) -> bool:
        self.is_armed = True
        return True

    def disarm(self) -> bool:
        self.is_armed = False
        return True

    def configure_dynamic_axis(self, cmd: DynamicAxisConfigCommand) -> dict:
        self.configured_axes.append(cmd)
        return {"type": "ack", "status": "ok"}

    def set_dynamic_position(self, cmd: DynamicPositionCommand) -> dict:
        self.positions.append(cmd)
        return {"type": "ack", "status": "ok"}

    def stage_dynamic_target(self, cmd: DynamicTargetCommand) -> dict:
        self.staged_targets.append(cmd)
        return {"type": "ack", "status": "staged"}

    def start_dynamic_motion(self, cmd: DynamicStartCommand, timeout_s: float, stop_requested: object) -> dict:
        self.started_motions.append(cmd)
        return self.mock_start_result


class TestDynamicScurveMotion(unittest.TestCase):
    def setUp(self) -> None:
        self.backend = MockBackend()

        def make_axis(name: str, scurve: bool, steps_per_mm: float = 64.705882):
            axis = MagicMock()
            axis.config = SimpleNamespace(
                name=name,
                scurve_enabled=scurve,
                steps_per_mm=steps_per_mm,
                max_travel_mm=1700.0,
                max_speed_mm_s=250.0,
                commissioned_max_speed_mm_s=200.0,
                default_speed_mm_s=50.0,
                acceleration=300.0,
                deceleration=300.0,
                scurve_max_jerk_mm_s3=1500.0,
                forward_direction=0,
                home_direction=1,
                settle_delay=0.01,
                max_pulse_hz=50000.0,
            )
            axis.motion_backend = self.backend
            axis.is_homed = True
            axis.position_mm = 100.0
            axis.position_steps = int(100.0 * steps_per_mm)
            axis.head_limit = SimpleNamespace(value=0)
            axis.tail_limit = SimpleNamespace(value=0)
            axis.direction = SimpleNamespace(value=False)
            return axis

        self.mock_x = make_axis("x", scurve=True)
        self.mock_y = make_axis("y", scurve=True)
        self.mock_z = make_axis("z", scurve=False, steps_per_mm=9.0)

        # Build mock machine config
        self.mock_config = SimpleNamespace(
            x=self.mock_x.config,
            y=self.mock_y.config,
            z=self.mock_z.config,
            home_order=["z", "x", "y"],
            slots={},
            safe_z_mm=10.0,
        )

        with patch("narit_vending.motion.HomingOrchestrator"):
            self.mc = MotionController(
                config=self.mock_config,
                x=self.mock_x,
                y=self.mock_y,
                z=self.mock_z,
                estop=SimpleNamespace(value=0),
            )

    def test_sync_dynamic_config(self) -> None:
        self.mc._sync_dynamic_config()
        self.assertEqual(len(self.backend.configured_axes), 2)
        x_cfg = self.backend.configured_axes[0]
        self.assertEqual(x_cfg.axis, "x")
        self.assertEqual(x_cfg.max_acceleration_millihz_s, int(round(300.0 * self.mock_x.config.steps_per_mm * 1000)))
        self.assertEqual(x_cfg.max_jerk_millihz_s2, int(round(1500.0 * self.mock_x.config.steps_per_mm * 1000)))

    def test_sync_dynamic_position(self) -> None:
        self.mc._sync_dynamic_position("x")
        self.assertEqual(len(self.backend.positions), 1)
        self.assertEqual(self.backend.positions[0].axis, "x")
        self.assertEqual(self.backend.positions[0].estimated_position_pulses, int(round(100.0 * self.mock_x.config.steps_per_mm)))

    def test_single_axis_xy_move_routes_to_dynamic_scurve(self) -> None:
        # Single axis X move
        plan = CoordinatedMovePlan(
            axes={"x": AxisMovePlan(axis="x", current_mm=100.0, target_mm=200.0, distance_mm=100.0, direction=0, steps=6471, speed_mm_s=100.0, duration_s=1.0)},
            duration_s=1.0,
            mode="speed",
        )
        self.mc._execute_coordinated_plan(plan)

        self.assertEqual(len(self.backend.staged_targets), 1)
        self.assertEqual(self.backend.staged_targets[0].axis, "x")
        self.assertEqual(self.backend.staged_targets[0].target_position_pulses, int(round(200.0 * self.mock_x.config.steps_per_mm)))
        self.assertEqual(len(self.backend.started_motions), 1)
        self.assertEqual(self.backend.started_motions[0].axes, ("x",))

    def test_dual_axis_xy_move_routes_to_dynamic_scurve(self) -> None:
        plan = CoordinatedMovePlan(
            axes={
                "x": AxisMovePlan(axis="x", current_mm=100.0, target_mm=200.0, distance_mm=100.0, direction=0, steps=6471, speed_mm_s=50.0, duration_s=2.0),
                "y": AxisMovePlan(axis="y", current_mm=100.0, target_mm=300.0, distance_mm=200.0, direction=0, steps=12941, speed_mm_s=100.0, duration_s=2.0),
            },
            duration_s=2.0,
            mode="speed",
        )
        self.mc._execute_coordinated_plan(plan)

        self.assertEqual(len(self.backend.staged_targets), 2)
        staged_axes = {cmd.axis for cmd in self.backend.staged_targets}
        self.assertEqual(staged_axes, {"x", "y"})
        self.assertEqual(len(self.backend.started_motions), 1)
        self.assertEqual(set(self.backend.started_motions[0].axes), {"x", "y"})

    def test_move_with_z_does_not_route_to_dynamic_scurve(self) -> None:
        self.backend.move_parallel = MagicMock(return_value={"status": "ok", "steps": {"x": 100, "z": 50}})
        plan = CoordinatedMovePlan(
            axes={
                "x": AxisMovePlan(axis="x", current_mm=100.0, target_mm=101.0, distance_mm=1.0, direction=0, steps=100, speed_mm_s=1.0, duration_s=1.0),
                "z": AxisMovePlan(axis="z", current_mm=10.0, target_mm=15.0, distance_mm=5.0, direction=0, steps=50, speed_mm_s=5.0, duration_s=1.0),
            },
            duration_s=1.0,
            mode="speed",
        )
        self.mc._execute_coordinated_plan(plan)

        self.assertEqual(len(self.backend.staged_targets), 0)
        self.assertEqual(len(self.backend.started_motions), 0)
        self.backend.move_parallel.assert_called_once()

    def test_stopped_due_to_limit_raises_and_clears_homed(self) -> None:
        self.backend.mock_start_result = {"status": "stopped", "stopped": True}
        plan = CoordinatedMovePlan(
            axes={"x": AxisMovePlan(axis="x", current_mm=100.0, target_mm=200.0, distance_mm=100.0, direction=0, steps=6471, speed_mm_s=100.0, duration_s=1.0)},
            duration_s=1.0,
            mode="speed",
        )
        with self.assertRaises(LimitTriggeredError):
            self.mc._execute_coordinated_plan(plan)

        self.assertFalse(self.mock_x.is_homed)


if __name__ == "__main__":
    unittest.main()
