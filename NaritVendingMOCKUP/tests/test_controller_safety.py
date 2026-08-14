import unittest

from narit_vending.controller.safety import SafetyInterlock
from narit_vending.controller.__main__ import _normalize_machine_state
from narit_vending.shared.commands import CommandEnvelope
from narit_vending.shared.snapshot import AxisSnapshot, MachineSnapshot


def _make_snapshot(**kwargs) -> MachineSnapshot:
    default_axes = {
        "x": AxisSnapshot("x", 0.0, 0, True, False, False),
        "y": AxisSnapshot("y", 0.0, 0, True, False, False),
        "z": AxisSnapshot("z", 0.0, 0, True, False, False),
    }
    defaults = {
        "state": "READY",
        "estop": False,
        "axes": default_axes,
        "busy": False,
        "active_command": None,
        "command_id": None,
        "command_started_at": None,
        "command_estimated_duration_s": None,
        "operation_phase": "ready",
        "operation_message": "Ready",
        "operation_axis": None,
        "homing": {"x": "passed", "y": "passed", "z": "passed"},
        "last_error": "",
        "alarm_channels": [],
        "config_revision": "rev1",
        "motor_test_armed": False,
        "configuration_restart_required": False,
        "stop_requested": False,
        "controlled_stop_requested": False,
        "speed_override": None,
    }
    defaults.update(kwargs)
    return MachineSnapshot(**defaults)


class TestControllerSafety(unittest.TestCase):
    def setUp(self):
        self.safety = SafetyInterlock()

    def test_priority_commands_always_allowed(self):
        snap = _make_snapshot(estop=True, busy=True, state="ALARM")
        for cmd in ("STOP", "E_STOP", "CLEAR_ALARM", "CONTROLLED_STOP"):
            env = CommandEnvelope(command_type=cmd, source="http", parameters={})
            dec = self.safety.evaluate(env, snap)
            self.assertTrue(dec.allowed, f"Priority command {cmd} should be allowed even in E_STOP")

    def test_estop_blocks_motion(self):
        snap = _make_snapshot(estop=True)
        env = CommandEnvelope(command_type="MOVE_TO", source="http", parameters={"x_mm": 10})
        dec = self.safety.evaluate(env, snap)
        self.assertFalse(dec.allowed)
        self.assertIn("ESTOP_ACTIVE", dec.reason_codes)

    def test_unhomed_state_blocks_motion(self):
        unhomed_axes = {
            "x": AxisSnapshot("x", 0.0, 0, False, False, False),
            "y": AxisSnapshot("y", 0.0, 0, True, False, False),
            "z": AxisSnapshot("z", 0.0, 0, True, False, False),
        }
        snap = _make_snapshot(state="NOT_READY", axes=unhomed_axes)
        env = CommandEnvelope(command_type="MOVE_TO_SLOT", source="http", parameters={"slot_code": "01"})
        dec = self.safety.evaluate(env, snap)
        self.assertFalse(dec.allowed)
        self.assertIn("AXES_NOT_HOMED", dec.reason_codes)

    def test_busy_blocks_new_motion(self):
        snap = _make_snapshot(busy=True)
        env = CommandEnvelope(command_type="JOG", source="http", parameters={"axis": "x", "distance_mm": 5})
        dec = self.safety.evaluate(env, snap)
        self.assertFalse(dec.allowed)
        self.assertIn("MACHINE_BUSY", dec.reason_codes)

    def test_motor_test_armed_blocks_normal_motion(self):
        snap = _make_snapshot(motor_test_armed=True)
        env = CommandEnvelope(command_type="MOVE_TO", source="http", parameters={"x_mm": 10})
        dec = self.safety.evaluate(env, snap)
        self.assertFalse(dec.allowed)
        self.assertIn("MOTOR_TEST_ARMED", dec.reason_codes)

    def test_ready_state_allows_motion(self):
        snap = _make_snapshot(state="READY")
        env = CommandEnvelope(command_type="MOVE_TO", source="http", parameters={"x_mm": 10})
        dec = self.safety.evaluate(env, snap)
        self.assertTrue(dec.allowed)

    def test_slot_sequence_is_blocked_until_machine_is_ready(self):
        env = CommandEnvelope(command_type="RUN_SLOT_SEQUENCE", source="http", parameters={"slot_code": "01"})
        decision = self.safety.evaluate(env, _make_snapshot(state="NOT_READY"))
        self.assertFalse(decision.allowed)
        self.assertIn("AXES_NOT_HOMED", decision.reason_codes)

    def test_legacy_success_state_normalizes_to_ready_after_homing(self):
        state = _normalize_machine_state(
            "success",
            estop=False,
            busy=False,
            active_command=None,
            axes_homed=True,
        )

        self.assertEqual(state, "READY")

    def test_legacy_idle_state_stays_not_ready_until_all_axes_homed(self):
        state = _normalize_machine_state(
            "idle",
            estop=False,
            busy=False,
            active_command=None,
            axes_homed=False,
        )

        self.assertEqual(state, "NOT_READY")


if __name__ == "__main__":
    unittest.main()
