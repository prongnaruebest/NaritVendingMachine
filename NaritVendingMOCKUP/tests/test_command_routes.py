import unittest
from unittest.mock import MagicMock

from narit_vending.shared.commands import CommandResult
from narit_vending.shared.snapshot import AxisSnapshot, MachineSnapshot
from narit_vending.web.app import create_web_app


def _ready_snapshot() -> MachineSnapshot:
    axes = {axis: AxisSnapshot(axis, 0.0, 0, True, False, False) for axis in ("x", "y", "z")}
    return MachineSnapshot(
        state="READY",
        estop=False,
        axes=axes,
        busy=False,
        active_command=None,
        command_id=None,
        command_started_at=None,
        command_estimated_duration_s=None,
        operation_phase="ready",
        operation_message="Controller ready",
        operation_axis=None,
        homing={axis: "passed" for axis in axes},
        last_error="",
        alarm_channels=[],
        config_revision="test",
        motor_test_armed=False,
        configuration_restart_required=False,
        stop_requested=False,
        controlled_stop_requested=False,
        speed_override=100.0,
    )


class CommandRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = MagicMock()
        self.controller.snapshot.return_value = _ready_snapshot()
        app = create_web_app(self.controller)
        app.testing = True
        self.client = app.test_client()

    def test_validation_rejection_returns_http_400_with_reason(self) -> None:
        self.controller.submit_command.return_value = CommandResult.rejected(
            "command-1",
            "Target exceeds X soft limit",
        )

        response = self.client.post("/api/motion/validate", json={"x_mm": 999.0})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])
        self.assertEqual(response.get_json()["error"], "Target exceeds X soft limit")

    def test_preview_success_reports_preview_stage(self) -> None:
        self.controller.submit_command.return_value = CommandResult(
            accepted=True,
            command_id="command-2",
            state="COMPLETED",
            result={"plan": {"duration_s": 1.25}, "axes": {}},
        )

        response = self.client.post("/api/motion/preview", json={"x_mm": 10.0})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])
        self.assertEqual(response.get_json()["stage"], "preview")

    def test_arm_stops_when_validation_is_rejected(self) -> None:
        self.controller.submit_command.return_value = CommandResult.rejected(
            "command-3",
            "Axis Y is not homed",
        )

        response = self.client.post("/api/motion/arm", json={"y_mm": 10.0})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Axis Y is not homed")
        self.assertEqual(self.controller.submit_command.call_count, 1)

    def test_slot_sequence_is_submitted_to_controller(self) -> None:
        self.controller.submit_command.return_value = CommandResult(
            accepted=True,
            command_id="sequence-1",
            state="COMPLETED",
            result={"slot_code": "01", "hold_s": 3},
        )

        response = self.client.post("/api/slots/01/sequence", json={"speed_mm_s": 12})

        self.assertEqual(response.status_code, 200)
        envelope = self.controller.submit_command.call_args.args[0]
        self.assertEqual(envelope.command_type, "RUN_SLOT_SEQUENCE")
        self.assertEqual(envelope.parameters, {"slot_code": "01", "speed_mm_s": 12.0})


if __name__ == "__main__":
    unittest.main()
