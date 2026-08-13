import unittest
from unittest.mock import MagicMock

from narit_vending.controller.handlers.sequence import make_run_slot_sequence_handler
from narit_vending.shared.commands import CommandEnvelope


class SlotSequenceHandlerTests(unittest.TestCase):
    def test_handler_passes_slot_and_speed_to_controller_service(self):
        sequence_service = MagicMock()
        sequence_service.run.return_value = {"ok": True, "sequence": ["MOVE_X", "HOME_X"]}
        handler = make_run_slot_sequence_handler(sequence_service)

        result = handler(CommandEnvelope(
            command_type="RUN_SLOT_SEQUENCE",
            source="http",
            parameters={"slot_code": "05", "speed_mm_s": 15},
        ))

        self.assertTrue(result.ok())
        call = sequence_service.run.call_args
        self.assertEqual(call.args, ("05",))
        self.assertEqual(call.kwargs["speed_mm_s"], 15.0)
        self.assertIsNone(call.kwargs["phase_callback"])

    def test_handler_requires_slot_code(self):
        sequence_service = MagicMock()
        handler = make_run_slot_sequence_handler(sequence_service)

        result = handler(CommandEnvelope(command_type="RUN_SLOT_SEQUENCE", source="http", parameters={}))

        self.assertFalse(result.ok())
        self.assertEqual(result.state, "REJECTED")
        sequence_service.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
