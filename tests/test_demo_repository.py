import tempfile
import unittest
import sqlite3
from pathlib import Path

from narit_vending.persistence.demo_repository import DemoRepository


class DemoRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.repository = DemoRepository(Path(self.tempdir.name) / "demo.sqlite3")

    def tearDown(self):
        self.tempdir.cleanup()

    def test_session_and_samples_round_trip(self):
        self.repository.create_session(
            session_id="session-1",
            started_at="2026-01-01T00:00:00+00:00",
            state="STARTING",
            configuration={"mode": "random", "slots": ["1", "2"]},
            requested=2,
        )
        self.repository.add_sample(
            sample_id="sample-1",
            session_id="session-1",
            cycle_no=1,
            slot_code="2",
            started_at="2026-01-01T00:00:01+00:00",
            completed_at="2026-01-01T00:00:02+00:00",
            duration_s=1.0,
            result="PASSED",
            reason="",
        )
        self.repository.finish_session(
            session_id="session-1",
            ended_at="2026-01-01T00:00:03+00:00",
            state="COMPLETED",
            counters={"attempted": 1, "passed": 1, "failed": 0, "skipped": 0, "stopped": 0},
            final_reason="",
        )

        history = self.repository.history()
        self.assertEqual(history[0]["configuration"]["mode"], "random")
        self.assertEqual(history[0]["samples"][0]["slot_code"], "2")
        self.assertEqual(self.repository.sample_counts_by_slot(), {"2": 1})
        self.assertEqual(self.repository.export_sample_rows()[0][0], "session-1")

    def test_foreign_key_rejects_orphan_sample(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.add_sample(
                sample_id="orphan",
                session_id="missing",
                cycle_no=1,
                slot_code="1",
                started_at="now",
                completed_at="now",
                duration_s=0,
                result="FAILED",
                reason="missing session",
            )


if __name__ == "__main__":
    unittest.main()
