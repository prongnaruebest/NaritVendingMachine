import unittest
from unittest.mock import MagicMock

from narit_vending.motion import (
    ActiveLimitError,
    AxisController,
    AxisConfig,
    AxisMovePlan,
    CoordinatedMovePlan,
    MachineConfig,
    MotionController,
    MotionError,
    TravelBoundaryError,
    SlotPosition,
    _build_half_periods,
    _home_backoff_limit_steps,
)
from narit_vending.webapp import MotionService


class MotionCharacterizationTests(unittest.TestCase):
    @staticmethod
    def _axis_config(name: str, maximum: float) -> AxisConfig:
        pins = {"x": (16, 23, 17, 27), "y": (26, 24, 22, 9), "z": (18, 25, 11, 5)}
        pulse, direction, head, tail = pins[name]
        return AxisConfig(
            name=name,
            pulse_pin=pulse,
            direction_pin=direction,
            head_limit_pin=head,
            tail_limit_pin=tail,
            home_direction=0,
            forward_direction=1,
            steps_per_mm=80.0,
            max_travel_mm=maximum,
        )

    def _mock_controller(self) -> tuple[MotionController, dict[str, MagicMock]]:
        configs = {
            "x": self._axis_config("x", 220.0),
            "y": self._axis_config("y", 260.0),
            "z": self._axis_config("z", 200.0),
        }
        axes = {name: MagicMock(config=config) for name, config in configs.items()}
        for axis in axes.values():
            axis.is_homed = True
            axis.position_mm = 0.0
        config = MachineConfig(
            x=configs["x"],
            y=configs["y"],
            z=configs["z"],
            home_order=("z", "y", "x"),
            safe_z_mm=10.0,
            slots={"1": SlotPosition("1", 50.0, 75.0, 25.0)},
        )
        controller = MotionController(
            axes["x"],
            axes["y"],
            axes["z"],
            MagicMock(value=False),
            config,
        )
        return controller, axes

    def test_2000_hz_profile_preserves_requested_pulse_count(self) -> None:
        pulse_count = 300
        duration_seconds = pulse_count / 2000.0

        half_periods = _build_half_periods(pulse_count, duration_seconds)

        self.assertEqual(len(half_periods), pulse_count)
        self.assertTrue(all(delay > 0 for delay in half_periods))

    def test_home_allows_ten_mm_for_sensor_release_before_precision_latch(self) -> None:
        self.assertEqual(_home_backoff_limit_steps(200.0), 2000)

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

    def test_home_all_runs_z_then_y_then_x(self) -> None:
        controller, axes = self._mock_controller()
        order: list[str] = []
        for name, axis in axes.items():
            axis.home.side_effect = lambda progress=None, axis_name=name: order.append(axis_name)

        controller.home_all()

        self.assertEqual(order, ["z", "y", "x"])

    def test_coordinated_move_verifies_commissioned_position_feedback(self) -> None:
        controller, axes = self._mock_controller()
        verifier = MagicMock()
        verifier.begin.side_effect = lambda name: f"token-{name}" if name in {"x", "y"} else None
        for axis in axes.values():
            axis.completion_verifier = verifier
        plan = CoordinatedMovePlan(
            axes={
                "x": AxisMovePlan("x", 0, 10, 10, 1, 800, 10, 1),
                "y": AxisMovePlan("y", 0, 5, 5, 1, 400, 5, 1),
            },
            duration_s=1,
            mode="speed",
        )
        controller._execute_coordinated_plan(plan)

        self.assertEqual(verifier.begin.call_count, 2)
        self.assertEqual(verifier.verify.call_count, 2)

    def test_continuous_jog_uses_authoritative_remaining_travel(self) -> None:
        axis = MagicMock()
        axis.is_homed = True
        axis.position_mm = 120.465
        axis.position_steps = 8282
        axis.config.max_travel_mm = 1590.0
        axis.mm_to_steps.side_effect = lambda mm: round(mm * 68.75)
        axis.steps_to_mm.side_effect = lambda steps: steps / 68.75
        service = MotionService.__new__(MotionService)
        service.controller = MagicMock()
        service.controller.axes.return_value = {"y": axis}
        service._run = lambda _name, fn: {"ok": True, "result": fn()}

        service.jog("y", 1469.535, speed_mm_s=30.0, continuous=True)

        expected = (round(1590.0 * 68.75) - 8282) / 68.75
        axis.move_mm.assert_called_once_with(expected, speed_mm_s=30.0, time_s=None)

    def test_software_travel_rejection_has_a_distinct_non_hardware_error(self) -> None:
        config = self._axis_config("z", 160.0)
        axis = AxisController.__new__(AxisController)
        axis.config = config
        axis.position_steps = round(160.0 * config.steps_per_mm)
        axis.is_homed = True
        axis.estop = MagicMock(value=False)
        axis.head_limit = MagicMock(value=False)
        axis.tail_limit = MagicMock(value=False)
        axis.stop_requested = lambda: False

        with self.assertRaises(TravelBoundaryError):
            axis.plan_relative_move(1.0, speed_mm_s=2.0)

    def test_active_limit_rejects_only_direction_into_sensor(self) -> None:
        config = self._axis_config("z", 160.0)
        axis = AxisController.__new__(AxisController)
        axis.config = config
        axis.position_steps = 0
        axis.is_homed = True
        axis.estop = MagicMock(value=False)
        axis.head_limit = MagicMock(value=True)
        axis.tail_limit = MagicMock(value=False)
        axis.stop_requested = lambda: False

        with self.assertRaises(ActiveLimitError):
            axis.plan_relative_move(-1.0, speed_mm_s=2.0)
        away = axis.plan_relative_move(1.0, speed_mm_s=2.0)
        self.assertEqual(away.steps, 80)

    def test_active_max_limit_allows_motion_back_toward_min(self) -> None:
        config = self._axis_config("x", 1700.0)
        axis = AxisController.__new__(AxisController)
        axis.config = config
        axis.position_steps = axis.mm_to_steps(1700.0)
        axis.is_homed = True
        axis.estop = MagicMock(value=False)
        axis.head_limit = MagicMock(value=False)
        axis.tail_limit = MagicMock(value=True)
        axis.stop_requested = lambda: False

        with self.assertRaises(ActiveLimitError):
            axis.plan_relative_move(1.0, speed_mm_s=5.0)
        away = axis.plan_relative_move(-1.0, speed_mm_s=5.0)
        self.assertEqual(away.steps, 80)

    def test_move_to_slot_uses_safe_z_then_xy_then_target_z(self) -> None:
        controller, axes = self._mock_controller()
        events: list[tuple] = []
        axes["z"].move_to_mm.side_effect = lambda target, **kwargs: events.append(("z", target))
        controller.move_to = MagicMock(
            side_effect=lambda **kwargs: events.append(("xy", kwargs["x_mm"], kwargs["y_mm"]))
        )

        controller.move_to_slot("1", speed_mm_s=10.0)

        self.assertEqual(events, [("z", 10.0), ("xy", 50.0, 75.0), ("z", 25.0)])

    def test_move_to_slot_skips_z_when_target_is_the_current_step(self) -> None:
        controller, axes = self._mock_controller()
        axes["z"].position_mm = 25.0
        axes["z"].position_steps = 2000
        axes["z"].mm_to_steps.return_value = 2000
        controller.move_to = MagicMock()

        controller.move_to_slot("1", speed_mm_s=10.0)

        controller.move_to.assert_called_once()
        axes["z"].move_to_mm.assert_not_called()

    def test_coordinated_move_uses_shared_nucleo_backend_not_gpio_pulses(self) -> None:
        controller, axes = self._mock_controller()
        backend = MagicMock(expected_protocol=3)
        backend.move_parallel.return_value = {"ok": True, "steps": {"x": 800, "y": 400}}
        for axis in axes.values():
            axis.motion_backend = backend
            axis.position_steps = 0
            axis.head_limit.value = False
            axis.tail_limit.value = False

        plan = CoordinatedMovePlan(
            axes={
                "x": AxisMovePlan("x", 0.0, 10.0, 10.0, 1, 800, 10.0, 1.0),
                "y": AxisMovePlan("y", 0.0, 5.0, 5.0, 1, 400, 5.0, 1.0),
            },
            duration_s=1.0,
            mode="speed",
        )

        controller._execute_coordinated_plan(plan)

        backend.move_parallel.assert_called_once()
        axes["x"].pulse.on.assert_not_called()
        axes["y"].pulse.on.assert_not_called()
        self.assertEqual(axes["x"].position_steps, 800)
        self.assertEqual(axes["y"].position_steps, 400)

    def test_same_row_slot_move_does_not_send_zero_step_axis_to_nucleo(self) -> None:
        controller, axes = self._mock_controller()
        backend = MagicMock(expected_protocol=3)
        backend.move_parallel.return_value = {"ok": True, "steps": {"x": 800}}
        for axis in axes.values():
            axis.motion_backend = backend
            axis.position_steps = 0
            axis.head_limit.value = False
            axis.tail_limit.value = False

        plan = CoordinatedMovePlan(
            axes={
                "x": AxisMovePlan("x", 0.0, 10.0, 10.0, 1, 800, 10.0, 1.0),
                "y": AxisMovePlan("y", 5.0, 5.0, 0.0, 1, 0, 0.0, 1.0),
            },
            duration_s=1.0,
            mode="speed",
        )

        controller._execute_coordinated_plan(plan)

        sent_plans = backend.move_parallel.call_args.args[0]
        self.assertEqual(set(sent_plans), {"x"})
        self.assertEqual(axes["x"].position_steps, 800)
        self.assertEqual(axes["y"].position_steps, 0)

    def test_motion_service_move_to_slot_returns_json_safe_slot(self) -> None:
        slot = SlotPosition("1", 21.9, 22.0, 35.0)

        class FakeController:
            def move_to_slot(self, slot_code, speed_mm_s=None, time_s=None):
                self.arguments = (slot_code, speed_mm_s, time_s)
                return slot

        class FakeService:
            controller = FakeController()

            @staticmethod
            def _run(_command_name, action):
                return {"ok": True, "result": action()}

        result = MotionService.move_to_slot(FakeService(), "1", speed_mm_s=2.0)

        self.assertEqual(result["result"], slot.to_dict())
        self.assertEqual(FakeService.controller.arguments, ("1", 2.0, None))

    def test_mqtt_slot_request_uses_return_home_sequence(self) -> None:
        callback = MagicMock()

        class FakeService:
            run_slot_sequence = MagicMock(return_value={"ok": True})

        result = MotionService.move_to_slot(
            FakeService(), "1", speed_mm_s=8.0, request_id="mqtt-1", phase_callback=callback
        )

        self.assertEqual(result, {"ok": True})
        FakeService.run_slot_sequence.assert_called_once_with(
            "1", speed_mm_s=8.0, request_id="mqtt-1", phase_callback=callback
        )


if __name__ == "__main__":
    unittest.main()
