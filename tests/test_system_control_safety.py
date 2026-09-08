import threading
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from narit_vending.webapp import MotionService


class SystemControlSafetyTests(unittest.TestCase):
    def service(self):
        service = MotionService.__new__(MotionService)
        service.lock = threading.RLock()
        service.command_lock = threading.Lock()
        service.controller = MagicMock()
        service.controller.axes.return_value = {
            name: SimpleNamespace(is_homed=True) for name in ("x", "y", "z")
        }
        service.nucleo_link = MagicMock()
        service.nucleo_link.status_payload.return_value = {"moving": {"x": 0, "y": 0, "z": 0}}
        service.io_backend = MagicMock()
        service.io_backend.communication_ok = True
        service.io_backend.input_active.return_value = False
        service.io_backend.alarm_channels.return_value = []
        service.nucleo_link.communication_ok = True
        service.picontrol_io = MagicMock()
        service.picontrol_io.outputs = {
            "xy_drive_power": {"reset_off_s": 1.0, "recovery_timeout_s": 2.0}
        }
        service.picontrol_io.alarm_channels.return_value = []
        service.homing = {name: "passed" for name in ("x", "y", "z")}
        service.motion_enabled = True
        service._safety_trip_latched = False
        service.armed_move = {"token": "old"}
        service.motor_test_armed = True
        service.busy = False
        service.last_error = ""
        service.operation_phase = "ready"
        service.operation_message = "ready"
        return service

    def test_di10_trip_stops_disarms_all_axes_and_invalidates_home(self):
        service = self.service()

        service._latch_emergency_stop()

        service.controller.request_stop.assert_called_once_with()
        service.nucleo_link.stop.assert_called_once_with()
        service.nucleo_link.disarm.assert_called_once_with()
        self.assertTrue(service._safety_trip_latched)
        self.assertFalse(service.motion_enabled)
        self.assertIsNone(service.armed_move)
        self.assertFalse(service.motor_test_armed)
        self.assertTrue(all(not axis.is_homed for axis in service.controller.axes().values()))

    def test_enable_is_rejected_while_di10_estop_is_active(self):
        service = self.service()
        service.io_backend.input_active.return_value = True

        result = service.enable_motion()

        self.assertFalse(result["ok"])
        service.controller.clear_stop.assert_not_called()

    def test_reset_usb_link_stops_first_and_leaves_motion_disabled(self):
        service = self.service()
        service.nucleo_link.reset_connection.return_value = {
            "ok": True, "physical_nrst": False, "reset_type": "usb_reconnect_and_handshake"
        }

        result = service.reset_nucleo_link()

        service.controller.request_stop.assert_called_once_with()
        service.nucleo_link.stop.assert_called_once_with()
        service.nucleo_link.reset_connection.assert_called_once_with()
        self.assertTrue(result["ok"])
        self.assertFalse(result["motion_enabled"])
        self.assertFalse(result["physical_nrst"])

    def test_reset_xy_drive_power_cycles_do0_and_invalidates_xy_home(self):
        service = self.service()

        with unittest.mock.patch("narit_vending.webapp.time.sleep"):
            result = service.reset_xy_drive_power()

        self.assertTrue(result["ok"])
        self.assertFalse(result["motion_enabled"])
        self.assertEqual(
            service.picontrol_io.set_output.call_args_list,
            [unittest.mock.call("xy_drive_power", False), unittest.mock.call("xy_drive_power", True)],
        )
        self.assertFalse(service.controller.axes()["x"].is_homed)
        self.assertFalse(service.controller.axes()["y"].is_homed)
        self.assertTrue(service.controller.axes()["z"].is_homed)


if __name__ == "__main__":
    unittest.main()
