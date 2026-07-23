import unittest

from narit_vending.shared.snapshot import AxisSnapshot, MachineSnapshot


class TestSharedSnapshot(unittest.TestCase):
    def test_axis_snapshot_serialization(self):
        ax = AxisSnapshot(
            name="x",
            position_mm=123.45,
            position_steps=12345,
            is_homed=True,
            head_limit=False,
            tail_limit=False,
        )
        d = ax.to_dict()
        self.assertEqual(d["name"], "x")
        self.assertEqual(d["position_mm"], 123.45)
        self.assertEqual(d["position_steps"], 12345)
        self.assertTrue(d["is_homed"])

        ax2 = AxisSnapshot.from_dict(d)
        self.assertEqual(ax, ax2)

    def test_machine_snapshot_offline_sentinel(self):
        snap = MachineSnapshot.offline()
        self.assertEqual(snap.state, "CONTROLLER_OFFLINE")
        self.assertFalse(snap.estop)
        self.assertIn("x", snap.axes)
        self.assertIn("Controller process is unreachable", snap.operation_message)

    def test_machine_snapshot_to_dict_flattening(self):
        axes = {
            "x": AxisSnapshot("x", 10.0, 100, True, False, False),
            "y": AxisSnapshot("y", 20.0, 200, True, False, False),
            "z": AxisSnapshot("z", 30.0, 300, True, False, False),
        }
        snap = MachineSnapshot(
            state="READY",
            estop=False,
            axes=axes,
            busy=False,
            active_command=None,
            command_id=None,
            command_started_at=None,
            command_estimated_duration_s=None,
            operation_phase="ready",
            operation_message="Ready",
            operation_axis=None,
            homing={"x": "passed", "y": "passed", "z": "passed"},
            last_error="",
            alarm_channels=[],
            config_revision="rev1",
            motor_test_armed=False,
            configuration_restart_required=False,
            stop_requested=False,
            controlled_stop_requested=False,
            speed_override=None,
        )
        d = snap.to_dict()
        self.assertEqual(d["state"], "READY")
        self.assertIn("x", d)
        self.assertEqual(d["x"]["position_mm"], 10.0)

        snap2 = MachineSnapshot.from_dict(d)
        self.assertEqual(snap2.state, "READY")
        self.assertEqual(snap2.axes["x"].position_mm, 10.0)


if __name__ == "__main__":
    unittest.main()
