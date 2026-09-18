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

    def test_save_slot_sequence_handler_saves_config(self):
        from narit_vending.controller.handlers.slots import make_save_slot_sequence_handler

        motion_service = MagicMock()
        motion_service.save_slot_sequence.return_value = {
            "ok": True,
            "slot_sequence": {"enabled": True, "z_standby_mm": 85.0},
        }
        handler = make_save_slot_sequence_handler(motion_service)

        result = handler(CommandEnvelope(
            command_type="SAVE_SLOT_SEQUENCE",
            source="http",
            parameters={"enabled": True, "z_standby_mm": 85.0},
        ))

        self.assertTrue(result.ok())
        self.assertEqual(result.state, "COMPLETED")
        motion_service.save_slot_sequence.assert_called_once_with(
            payload={"enabled": True, "z_standby_mm": 85.0}
        )

    def test_move_to_slot_delegates_to_sequence_when_enabled(self):
        from narit_vending.controller.handlers.move import make_move_to_slot_handler

        motion_service = MagicMock()
        motion_service.move_to_slot.return_value = {
            "ok": True,
            "slot_code": "02",
            "sequence": ["MOVE_XY_TARGET", "COMPLETED"],
        }
        handler = make_move_to_slot_handler(motion_service)

        result = handler(CommandEnvelope(
            command_type="MOVE_TO_SLOT",
            source="http",
            parameters={"slot_code": "02", "speed_mm_s": 20.0},
        ))

        self.assertTrue(result.ok())
        motion_service.move_to_slot.assert_called_once_with("02", speed_mm_s=20.0, time_s=None)


if __name__ == "__main__":
    unittest.main()
