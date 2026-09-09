import json
import tempfile
import unittest
from pathlib import Path

from narit_vending.persistence.slot_repository import JsonSlotRepository, SlotRevisionConflict


class SlotRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "machine.json"
        self.path.write_text(json.dumps({
            "axes": {"x": {"max_travel_mm": 1700}},
            "safe_z_mm": 10,
            "slots": {
                "1": {"x_mm": 1, "y_mm": 2, "z_mm": 3, "product_name": "old", "dispense_delay_ms": 0},
                "2": {"x_mm": 4, "y_mm": 5, "z_mm": 6, "product_name": "keep", "dispense_delay_ms": 10},
            },
        }), encoding="utf-8")
        self.repository = JsonSlotRepository(self.path)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_save_is_atomic_and_preserves_non_slot_configuration(self):
        revision = self.repository.revision()
        new_revision = self.repository.save_slot("1", {
            "x_mm": 100, "y_mm": 200, "z_mm": 30,
            "product_name": "new", "dispense_delay_ms": 25,
        }, expected_revision=revision)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertNotEqual(new_revision, revision)
        self.assertEqual(payload["axes"]["x"]["max_travel_mm"], 1700)
        self.assertEqual(payload["slots"]["2"]["product_name"], "keep")
        self.assertEqual(payload["slots"]["1"]["x_mm"], 100.0)

    def test_stale_revision_is_rejected_without_overwrite(self):
        stale = self.repository.revision()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        payload["safe_z_mm"] = 20
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(SlotRevisionConflict):
            self.repository.save_slot("1", {
                "x_mm": 0, "y_mm": 0, "z_mm": 0,
            }, expected_revision=stale)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["safe_z_mm"], 20)

    def test_unknown_slot_cannot_be_created_implicitly(self):
        with self.assertRaises(KeyError):
            self.repository.save_slot("99", {
                "x_mm": 0, "y_mm": 0, "z_mm": 0,
            }, expected_revision=self.repository.revision())


if __name__ == "__main__":
    unittest.main()
