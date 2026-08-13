import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from narit_vending.controller.sequence_service import SequenceService


class SequenceServiceTests(unittest.TestCase):
    def _service(self):
        events = []
        axes = {name: MagicMock(is_homed=True) for name in ("x", "y", "z")}
        for name, axis in axes.items():
            axis.move_to_mm.side_effect = lambda target, _name=name, **_: events.append(f"MOVE_{_name.upper()}")
        slot = SimpleNamespace(code="2", x_mm=10.0, y_mm=20.0, z_mm=30.0)
        controller = MagicMock()
        controller.config.slots = {"2": slot}
        controller.axes.return_value = axes
        controller.current_position.side_effect = [
            {"x_mm": 10.0, "y_mm": 20.0, "z_mm": 30.0},
            {"x_mm": 0.0, "y_mm": 0.0, "z_mm": 0.0},
        ]
        controller.stop_requested.return_value = False
        controller.emergency_stop_active.return_value = False
        controller.home_axis.side_effect = lambda axis, progress=None: events.append(f"HOME_{axis.upper()}")
        motion = MagicMock()
        motion.controller = controller
        motion._run.side_effect = lambda _name, action: {"ok": True, "result": action()}
        service = SequenceService(motion)
        return service, events

    @patch("narit_vending.controller.sequence_service.time.sleep")
    def test_runs_required_axis_order_and_returns_verification(self, _sleep):
        service, events = self._service()
        phases = []

        result = service.run("2", phase_callback=lambda _state, detail: phases.append(detail["phase"]))

        self.assertTrue(result["ok"])
        self.assertEqual(events, ["MOVE_X", "MOVE_Y", "MOVE_Z", "HOME_Z", "HOME_Y", "HOME_X"])
        self.assertEqual(phases, ["MOVE_X", "MOVE_Y", "MOVE_Z", "HOLD_AT_TARGET", "HOME_Z", "HOME_Y", "HOME_X", "COMPLETED"])
        self.assertTrue(result["result"]["target_verification"]["target_reached"])
        self.assertTrue(result["result"]["home_verification"]["home_reached"])


if __name__ == "__main__":
    unittest.main()
