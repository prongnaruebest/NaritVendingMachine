from __future__ import annotations

import unittest
from unittest.mock import patch

from narit_vending.picontrol_io import PiControlIOBackend


class FakeInput:
    values = {13: False, 17: False, 27: False, 22: False}

    def __init__(self, pin: int, pull_up: bool = False) -> None:
        self.pin = pin

    @property
    def value(self) -> bool:
        return self.values[self.pin]

    def close(self) -> None:
        pass


class FaultingInput(FakeInput):
    @property
    def value(self) -> bool:
        raise OSError("local GPIO read failed")


def config() -> dict:
    return {
        "poll_interval_s": 0.02,
        "inputs": {
            "x_alarm": {"channel": 0, "pin": 13, "active_state": True, "fail_safe": True, "label": "X_DRIVE_ALM"},
            "y_alarm": {"channel": 1, "pin": 17, "active_state": True, "fail_safe": True, "label": "Y_DRIVE_ALM"},
            "x_pend": {"channel": 2, "pin": 27, "active_state": True, "fail_safe": False, "label": "X_PEND"},
            "y_pend": {"channel": 3, "pin": 22, "active_state": True, "fail_safe": False, "label": "Y_PEND"},
        },
    }


class PiControlIOBackendTests(unittest.TestCase):
    @patch("narit_vending.picontrol_io.DigitalInputDevice", FaultingInput)
    def test_gpio_read_failure_is_fail_safe_for_drive_alarms(self) -> None:
        backend = PiControlIOBackend(config())
        backend._poll_once()

        self.assertFalse(backend.communication_ok)
        self.assertTrue(backend.input_active("x_alarm"))
        self.assertTrue(next(item for item in backend.alarm_channels() if item["code"] == "PICTRL-DI")["active"])
        self.assertIn("GPIO read failed", backend.status_payload()["last_error"])

    @patch("narit_vending.picontrol_io.DigitalInputDevice", FakeInput)
    def test_status_identifies_local_channels_and_poll_timing(self) -> None:
        backend = PiControlIOBackend(config())
        backend._poll_once()
        status = backend.status_payload()
        self.assertTrue(status["communication_ok"])
        self.assertIsNotNone(status["last_success_at"])
        self.assertIsInstance(status["poll_latency_ms"], float)
        self.assertEqual(status["input_details"]["x_alarm"]["raw_channel"], "DI0")
        self.assertEqual(status["input_details"]["x_alarm"]["pin"], 13)
        self.assertEqual(status["input_details"]["x_pend"]["raw_channel"], "DI2")

    @patch("narit_vending.picontrol_io.DigitalInputDevice", FakeInput)
    def test_drive_alarm_logical_state_is_separate_and_fail_safe(self) -> None:
        backend = PiControlIOBackend(config())
        FakeInput.values[13] = True
        try:
            backend._poll_once()
            self.assertTrue(backend.status_payload()["inputs"]["x_alarm"])
            self.assertTrue(next(item for item in backend.alarm_channels() if item["code"] == "DRV-X")["active"])
        finally:
            FakeInput.values[13] = False

    @patch("narit_vending.picontrol_io.DigitalInputDevice", FakeInput)
    def test_pend_is_position_feedback_and_never_a_drive_alarm(self) -> None:
        backend = PiControlIOBackend(config())
        FakeInput.values[27] = True
        try:
            backend._poll_once()
            status = backend.status_payload()
            self.assertTrue(status["inputs"]["x_pend"])
            self.assertEqual(status["position_channels"][0]["state"], "in_position")
            self.assertFalse(status["position_channels"][0]["blocking"])
            self.assertFalse(status["position_channels"][0]["commissioned"])
            self.assertEqual(status["input_details"]["x_pend"]["safety_class"], "advisory")
            self.assertNotIn("PEND-X", {item["code"] for item in backend.alarm_channels()})
        finally:
            FakeInput.values[27] = False

    @patch("narit_vending.picontrol_io.DigitalInputDevice", FakeInput)
    def test_pend_transition_diagnostics_are_recorded(self) -> None:
        payload = config()
        payload["inputs"]["x_pend"]["commissioned"] = True
        payload["inputs"]["x_pend"]["settle_timeout_ms"] = 750
        backend = PiControlIOBackend(payload)
        FakeInput.values[27] = False
        try:
            backend._poll_once()
            FakeInput.values[27] = True
            backend._poll_once()
            channel = backend.position_channels()[0]
            self.assertTrue(channel["commissioned"])
            self.assertEqual(channel["settle_timeout_ms"], 750)
            self.assertEqual(channel["transitions"], 1)
            self.assertEqual(channel["active_events"], 1)
            self.assertIsNotNone(channel["last_change_at"])
            self.assertIsNotNone(channel["active_since_at"])
        finally:
            FakeInput.values[27] = False


if __name__ == "__main__":
    unittest.main()
