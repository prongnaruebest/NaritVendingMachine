import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from narit_vending.controller.sequence_service import SequenceService
from narit_vending.domain.errors import EmergencyStopError, ControlledStopError
from narit_vending.motion import SlotSequenceConfig


class SequenceServiceTests(unittest.TestCase):
    def _service(self):
        events = []
        axes = {name: MagicMock(is_homed=True) for name in ("x", "y", "z")}
        axes["y"].config = SimpleNamespace(max_travel_mm=1700.0)
        axes["z"].config = SimpleNamespace(max_travel_mm=160.0)
        axes["x"].config = SimpleNamespace(max_travel_mm=1780.0)

        axes["z"].move_to_mm.side_effect = lambda target, **_: events.append(f"MOVE_Z_{target}")
        axes["y"].move_to_mm.side_effect = lambda target, **_: events.append(f"MOVE_Y_{target}")
        axes["x"].move_to_mm.side_effect = lambda target, **_: events.append(f"MOVE_X_{target}")

        slot = SimpleNamespace(code="2", x_mm=100.0, y_mm=200.0, z_mm=85.0)
        seq_cfg = SlotSequenceConfig(
            enabled=True,
            z_standby_mm=85.0,
            z_pick_mm=20.0,
            y_lift_delta_mm=30.0,
            pick_hold_seconds=3.0,
            parking_x_mm=50.0,
            parking_y_mm=50.0,
            z_drop_mm=150.0,
            drop_hold_seconds=3.0,
        )
        controller = MagicMock()
        controller.config = SimpleNamespace(
            slots={"2": slot},
            slot_sequence=seq_cfg,
            home_order=("z", "y", "x"),
        )
        controller.axes.return_value = axes
        controller.current_position.side_effect = [
            {"x_mm": 0.0, "y_mm": 0.0, "z_mm": 0.0},  # initial at home
            {"x_mm": 0.0, "y_mm": 0.0, "z_mm": 0.0},  # home verification
        ]
        controller.move_to.side_effect = lambda x_mm=None, y_mm=None, **_: events.append(f"MOVE_XY_({x_mm},{y_mm})")
        controller.stop_requested.return_value = False
        controller.emergency_stop_active.return_value = False
        controller.home_axis.side_effect = lambda axis, progress=None: events.append(f"HOME_{axis.upper()}")
        motion = MagicMock()
        motion.controller = controller
        motion._run.side_effect = lambda _name, action: {"ok": True, "result": action()}
        service = SequenceService(motion)
        return service, events

    @patch("narit_vending.controller.sequence_service.time.sleep")
    def test_runs_9_stage_cycle_in_correct_order(self, _sleep):
        service, events = self._service()
        phases = []

        result = service.run("2", phase_callback=lambda _state, detail: phases.append(detail["phase"]))

        self.assertTrue(result["ok"])
        self.assertEqual(events, [
            "MOVE_Z_85.0",            # Initial: move Z to standby
            "MOVE_XY_(100.0,200.0)",  # Stage 1: move XY to slot
            "MOVE_Z_20.0",            # Stage 2: extend Z to pick
            "MOVE_Y_230.0",           # Stage 3: Y lift (+30mm)
            "MOVE_Z_85.0",            # Stage 4: retract Z to standby
            "MOVE_XY_(50.0,50.0)",    # Stage 5: move XY to parking
            "MOVE_Z_150.0",           # Stage 6: extend Z to drop
            "MOVE_Z_85.0",            # Stage 7: retract Z to standby
            "HOME_Z",                 # Stage 8: home axes (Z -> Y -> X)
            "HOME_Y",
            "HOME_X",
        ])
        expected_phases = [
            "MOVE_Z_STANDBY",
            "MOVE_XY_TARGET",
            "EXTEND_Z_PICK",
            "Y_LIFT_PICK",
            "HOLD_AT_PICK",
            "RETRACT_Z_STANDBY",
            "MOVE_XY_PARKING",
            "EXTEND_Z_DROP",
            "HOLD_AT_DROP",
            "RETRACT_Z_DROP",
            "HOME_Z",
            "HOME_Y",
            "HOME_X",
            "COMPLETED",
        ]
        self.assertEqual(phases, expected_phases)
        service._motion.activate_dispense.assert_called_once_with()
        self.assertTrue(result["result"]["home_verification"]["home_reached"])

    def test_rejects_when_axes_unhomed(self):
        service, _ = self._service()
        service._motion.controller.axes()["x"].is_homed = False

        result = service.run("2")
        self.assertFalse(result["ok"])
        self.assertEqual(result["failed_phase"], "VALIDATE_READY")

    @patch("narit_vending.controller.sequence_service.time.sleep")
    def test_aborts_on_emergency_stop_during_dwell(self, _sleep):
        service, _ = self._service()
        service._motion._run.side_effect = lambda _name, action: action()
        # Trigger E-stop during dwell
        call_count = 0
        def estop_trigger():
            nonlocal call_count
            call_count += 1
            return call_count > 2
        service._motion.controller.emergency_stop_active.side_effect = estop_trigger

        with self.assertRaises(EmergencyStopError):
            service.run("2")


if __name__ == "__main__":
    unittest.main()

