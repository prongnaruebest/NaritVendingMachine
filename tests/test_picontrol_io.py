from __future__ import annotations

import unittest
from unittest.mock import patch

from narit_vending.picontrol_io import PiControlIOBackend


class FakeInput:
    values = {13: False, 17: False}

    def __init__(self, pin: int, pull_up: bool = False) -> None:
        self.pin = pin

    @property
    def value(self) -> bool:
        return self.values[self.pin]

    def close(self) -> None:
        pass


def config() -> dict:
    return {
        "poll_interval_s": 0.02,
        "inputs": {
            "x_alarm": {"channel": 0, "pin": 13, "active_state": True, "fail_safe": True, "label": "X_DRIVE_ALM"},
            "y_alarm": {"channel": 1, "pin": 17, "active_state": True, "fail_safe": True, "label": "Y_DRIVE_ALM"},
        },
    }


class PiControlIOBackendTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
