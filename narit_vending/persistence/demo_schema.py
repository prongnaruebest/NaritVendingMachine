"""Versioned schema registry for Demo Slot Sampling history."""

from .sqlite_migrations import Migration


DEMO_MIGRATIONS = (
    Migration(
        version=1,
        name="create_demo_sessions_and_samples",
        statements=(
            """CREATE TABLE IF NOT EXISTS demo_sessions (
                 session_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, ended_at TEXT,
                 state TEXT NOT NULL, configuration_json TEXT NOT NULL,
                 requested INTEGER NOT NULL DEFAULT 0, attempted INTEGER NOT NULL DEFAULT 0,
                 passed INTEGER NOT NULL DEFAULT 0, failed INTEGER NOT NULL DEFAULT 0,
                 skipped INTEGER NOT NULL DEFAULT 0, stopped INTEGER NOT NULL DEFAULT 0,
                 final_reason TEXT NOT NULL DEFAULT ''
               )""",
            """CREATE TABLE IF NOT EXISTS demo_samples (
                 sample_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, cycle_no INTEGER NOT NULL,
                 slot_code TEXT NOT NULL, started_at TEXT NOT NULL, completed_at TEXT,
                 duration_s REAL, result TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '',
                 FOREIGN KEY(session_id) REFERENCES demo_sessions(session_id)
               )""",
            "CREATE INDEX IF NOT EXISTS idx_demo_samples_session ON demo_samples(session_id)",
        ),
    ),
)
