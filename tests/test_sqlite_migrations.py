import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from narit_vending.persistence.sqlite_migrations import Migration, SQLiteMigrator


class SQLiteMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database = Path(self.tempdir.name) / "history.sqlite3"

    def tearDown(self):
        self.tempdir.cleanup()

    def test_migrations_apply_in_version_order_and_are_idempotent(self):
        migrations = (
            Migration(2, "add_value", ("ALTER TABLE records ADD COLUMN value TEXT",)),
            Migration(1, "create_records", ("CREATE TABLE records(id INTEGER PRIMARY KEY)",)),
        )
        migrator = SQLiteMigrator(self.database, migrations)

        self.assertEqual(migrator.migrate(), 2)
        self.assertEqual(migrator.migrate(), 2)

        with closing(sqlite3.connect(self.database)) as db:
            columns = [row[1] for row in db.execute("PRAGMA table_info(records)")]
            applied = list(db.execute("SELECT version,name FROM schema_migrations ORDER BY version"))
        self.assertEqual(columns, ["id", "value"])
        self.assertEqual(applied, [(1, "create_records"), (2, "add_value")])

    def test_existing_legacy_rows_survive_baseline_migration(self):
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("CREATE TABLE records(id INTEGER PRIMARY KEY, value TEXT)")
            db.execute("INSERT INTO records(value) VALUES('preserve-me')")
        migrator = SQLiteMigrator(
            self.database,
            (Migration(1, "legacy_baseline", ("CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY, value TEXT)",)),),
        )

        migrator.migrate()

        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute("SELECT value FROM records").fetchone()[0], "preserve-me")

    def test_failed_migration_does_not_record_version(self):
        migrator = SQLiteMigrator(
            self.database,
            (Migration(1, "broken", ("CREATE TABLE records(id INTEGER)", "INVALID SQL")),),
        )

        with self.assertRaises(sqlite3.DatabaseError):
            migrator.migrate()

        self.assertEqual(migrator.current_version(), 0)

    def test_changed_name_for_applied_version_is_rejected(self):
        SQLiteMigrator(
            self.database, (Migration(1, "original", ("CREATE TABLE records(id INTEGER)",)),)
        ).migrate()

        with self.assertRaisesRegex(RuntimeError, "name mismatch"):
            SQLiteMigrator(
                self.database, (Migration(1, "renamed", ("CREATE TABLE records(id INTEGER)",)),)
            ).migrate()


if __name__ == "__main__":
    unittest.main()
