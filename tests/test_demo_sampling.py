import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from narit_vending.controller.demo_service import DemoSamplingService


class FakeMotion:
    def __init__(self):
        axis = SimpleNamespace(max_travel_mm=100.0)
        sequence = SimpleNamespace(enabled=True, y_lift_delta_mm=5.0)
        slots = {
            "1": SimpleNamespace(x_mm=10.0, y_mm=10.0, z_mm=10.0),
            "2": SimpleNamespace(x_mm=20.0, y_mm=20.0, z_mm=20.0),
        }
        self.controller = SimpleNamespace(config=SimpleNamespace(
            slots=slots, x=axis, y=axis, z=axis, slot_sequence=sequence,
        ))
        self.motion_enabled = True
        self.moves = []
        self.stopped = False

    def _motion_safety_errors(self, **kwargs):
        return []

    def run_slot_sequence(self, slot, speed_mm_s=None, request_id=None, phase_callback=None):
        self.moves.append((slot, speed_mm_s))
        if phase_callback:
            phase_callback("moving", {"phase": "MOVE_XY_TARGET", "message": f"Moving to {slot}"})
        return {"ok": True}

    def stop(self):
        self.stopped = True
        return {"ok": True}


class DemoSamplingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.motion = FakeMotion()
        self.demo = DemoSamplingService(self.motion, Path(self.tmp.name) / "demo.sqlite3")

    def tearDown(self):
        self.demo.stop(stop_motion=False)
        if self.demo._thread:
            self.demo._thread.join(timeout=1)
        self.tmp.cleanup()

    def test_unbounded_demo_is_rejected(self):
        self.assertEqual(self.demo.status()["schema_version"], 1)
        result = self.demo.configure({"sample_count": 0, "max_duration_s": 0})
        self.assertFalse(result["ok"])
        self.assertIn("requires", result["error"])

    def test_sequential_demo_is_controller_owned_bounded_and_logged(self):
        self.assertTrue(self.demo.configure({"mode": "sequential", "slots": ["1", "2"], "sample_count": 2, "dwell_s": 0})["ok"])
        arm = self.demo.arm()
        self.assertTrue(arm["ok"])
        started = self.demo.start(arm["arm_token"])
        self.assertTrue(started["ok"])
        self.demo._thread.join(timeout=2)
        status = self.demo.status()
        self.assertEqual(status["state"], "COMPLETED")
        self.assertEqual(self.motion.moves, [("1", 5.0), ("2", 5.0)])
        self.assertEqual(status["counters"]["passed"], 2)
        self.assertEqual(len(self.demo.history()), 1)
        history = self.demo.history()[0]
        self.assertEqual(history["configuration"]["mode"], "sequential")
        self.assertEqual(history["configuration"]["workflow"], "slot_sequence")
        self.assertEqual([row["slot_code"] for row in history["samples"]], ["1", "2"])
        self.assertTrue(all(row["result"] == "PASSED" for row in history["samples"]))
        self.assertIn("session_id,cycle,slot", self.demo.export_csv())

    def test_random_sample_count_equals_number_of_target_moves(self):
        configured = self.demo.configure({
            "mode": "random", "slots": ["1", "2"], "sample_count": 7,
            "random_seed": 42, "dwell_s": 0,
        })
        self.assertTrue(configured["ok"])
        arm = self.demo.arm()
        self.demo.start(arm["arm_token"])
        self.demo._thread.join(timeout=2)

        status = self.demo.status()
        self.assertEqual(status["state"], "COMPLETED")
        self.assertEqual(status["counters"]["requested"], 7)
        self.assertEqual(status["counters"]["attempted"], 7)
        self.assertEqual(len(self.motion.moves), 7)
        self.assertTrue(all(self.motion.moves[index][0] != self.motion.moves[index - 1][0] for index in range(1, 7)))

    def test_start_rechecks_motion_safety_after_arm(self):
        self.demo.configure({"sample_count": 1})
        arm = self.demo.arm()
        self.motion.motion_enabled = False
        result = self.demo.start(arm["arm_token"])
        self.assertFalse(result["ok"])
        self.assertEqual(self.motion.moves, [])

    def test_demo_rejects_slots_that_cannot_complete_sequence(self):
        self.motion.controller.config.slots["3"] = SimpleNamespace(
            x_mm=10.0, y_mm=98.0, z_mm=10.0,
        )
        configured = self.demo.configure({"slots": ["3"], "sample_count": 1})

        self.assertTrue(configured["ok"])
        self.assertNotIn("3", configured["configuration"]["slots"])

    def test_demo_requires_enabled_slot_sequence(self):
        self.motion.controller.config.slot_sequence.enabled = False

        result = self.demo.configure({"sample_count": 1})

        self.assertFalse(result["ok"])
        self.assertIn("sequence-eligible", result["error"])

    def test_demo_duration_is_read_only_and_calculated_by_frontend(self):
        root = Path(__file__).resolve().parents[1]
        template = (root / "narit_vending" / "templates" / "index.html").read_text(encoding="utf-8")
        script = (root / "narit_vending" / "static" / "app.js").read_text(encoding="utf-8")

        duration_field = template.split('id="demo-max-duration"', 1)[1].split(">", 1)[0]
        self.assertIn("readonly", duration_field)
        self.assertIn("function calculateDemoMaxDuration()", script)
        self.assertIn("complete Controller-owned slot sequence", script)
        self.assertIn("max_duration_s: maxDuration", script)
        self.assertIn("const SLOT_COUNT = 40", script)
        self.assertIn("Slot Overview 8×5", template)
        self.assertIn("Slot Matrix 01–40", template)


if __name__ == "__main__":
    unittest.main()
