import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from narit_vending.controller.demo_service import DemoSamplingService


class FakeMotion:
    def __init__(self):
        self.controller = SimpleNamespace(config=SimpleNamespace(slots={"1": object(), "2": object()}))
        self.motion_enabled = True
        self.moves = []
        self.stopped = False

    def _motion_safety_errors(self, **kwargs):
        return []

    def move_to_slot(self, slot, speed_mm_s=None):
        self.moves.append((slot, speed_mm_s))
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


if __name__ == "__main__":
    unittest.main()
