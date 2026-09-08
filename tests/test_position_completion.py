import unittest
from unittest.mock import MagicMock, patch

from narit_vending.controller.position_completion import PendCompletionVerifier
from narit_vending.domain.errors import PositionVerificationError


class PositionCompletionTests(unittest.TestCase):
    def test_uncommissioned_channel_is_a_noop(self):
        backend = MagicMock(communication_ok=True)
        backend.position_channels.return_value = [{"axis": "x", "active": False, "commissioned": False}]
        verifier = PendCompletionVerifier(backend)
        self.assertIsNone(verifier.begin("x"))
        verifier.verify(None)

    def test_commissioned_active_pend_verifies(self):
        backend = MagicMock(communication_ok=True)
        backend.position_channels.return_value = [{
            "axis": "x", "active": True, "commissioned": True,
            "transitions": 4, "settle_timeout_ms": 500,
        }]
        verifier = PendCompletionVerifier(backend)
        token = verifier.begin("x")
        verifier.verify(token)

    @patch("narit_vending.controller.position_completion.sleep", return_value=None)
    @patch("narit_vending.controller.position_completion.monotonic", side_effect=[0.0, 0.0, 1.0])
    def test_inactive_pend_times_out(self, _clock, _sleep):
        backend = MagicMock(communication_ok=True)
        backend.position_channels.return_value = [{
            "axis": "y", "active": False, "commissioned": True,
            "transitions": 0, "settle_timeout_ms": 100,
        }]
        verifier = PendCompletionVerifier(backend)
        with self.assertRaisesRegex(PositionVerificationError, "PEND did not reach"):
            verifier.verify(verifier.begin("y"))

    def test_communication_loss_fails_verification(self):
        backend = MagicMock(communication_ok=True)
        backend.position_channels.return_value = [{
            "axis": "x", "active": False, "commissioned": True,
            "transitions": 0, "settle_timeout_ms": 500,
        }]
        verifier = PendCompletionVerifier(backend)
        token = verifier.begin("x")
        backend.communication_ok = False
        with self.assertRaisesRegex(PositionVerificationError, "communication lost"):
            verifier.verify(token)


if __name__ == "__main__":
    unittest.main()
