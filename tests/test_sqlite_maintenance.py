import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from narit_vending.persistence.sqlite_maintenance import SQLiteIntegrityError, SQLiteMaintenance


def create_database(path: Path, value: str) -> None:
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("CREATE TABLE records(value TEXT NOT NULL)")
        db.execute("INSERT INTO records(value) VALUES(?)", (value,))


def read_value(path: Path) -> str:
    with closing(sqlite3.connect(path)) as db:
        return str(db.execute("SELECT value FROM records").fetchone()[0])


class SQLiteMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.live = self.root / "controller.sqlite3"
        create_database(self.live, "original")
        self.maintenance = SQLiteMaintenance(self.live)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_backup_is_consistent_and_does_not_change_live_database(self):
        backup = self.maintenance.backup_to(self.root / "backups" / "controller.sqlite3")
        self.assertEqual(read_value(backup), "original")
        self.assertEqual(read_value(self.live), "original")

    def test_restore_replaces_live_database_and_keeps_safety_backup(self):
        candidate = self.root / "candidate.sqlite3"
        safety = self.root / "safety.sqlite3"
        create_database(candidate, "restored")

        self.maintenance.restore_from(candidate, safety_backup=safety)

        self.assertEqual(read_value(self.live), "restored")
        self.assertEqual(read_value(safety), "original")

    def test_corrupt_restore_is_rejected_without_changing_live_database(self):
        corrupt = self.root / "corrupt.sqlite3"
        corrupt.write_bytes(b"not a sqlite database")

        with self.assertRaises(SQLiteIntegrityError):
            self.maintenance.restore_from(corrupt)

        self.assertEqual(read_value(self.live), "original")

    def test_source_and_destination_must_differ(self):
        with self.assertRaises(ValueError):
            self.maintenance.backup_to(self.live)
        with self.assertRaises(ValueError):
            self.maintenance.restore_from(self.live)


if __name__ == "__main__":
    unittest.main()
