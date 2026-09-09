"""SQLite repository for Demo Slot Sampling sessions and samples."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from .demo_schema import DEMO_MIGRATIONS
from .sqlite_migrations import SQLiteMigrator


class DemoRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.schema_version = SQLiteMigrator(self.database_path, DEMO_MIGRATIONS).migrate()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def create_session(
        self,
        *,
        session_id: str,
        started_at: str,
        state: str,
        configuration: dict[str, Any],
        requested: int,
    ) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                """INSERT INTO demo_sessions(
                       session_id,started_at,state,configuration_json,requested
                   ) VALUES(?,?,?,?,?)""",
                (session_id, started_at, state, json.dumps(configuration, sort_keys=True), requested),
            )

    def sample_counts_by_slot(self) -> dict[str, int]:
        with closing(self._connect()) as db:
            return {
                str(row["slot_code"]): int(row["count"])
                for row in db.execute(
                    "SELECT slot_code,COUNT(*) count FROM demo_samples GROUP BY slot_code"
                )
            }

    def add_sample(
        self,
        *,
        sample_id: str,
        session_id: str,
        cycle_no: int,
        slot_code: str,
        started_at: str,
        completed_at: str,
        duration_s: float,
        result: str,
        reason: str,
    ) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                """INSERT INTO demo_samples(
                       sample_id,session_id,cycle_no,slot_code,started_at,
                       completed_at,duration_s,result,reason
                   ) VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    sample_id,
                    session_id,
                    cycle_no,
                    slot_code,
                    started_at,
                    completed_at,
                    duration_s,
                    result,
                    reason,
                ),
            )

    def finish_session(
        self,
        *,
        session_id: str,
        ended_at: str,
        state: str,
        counters: dict[str, int],
        final_reason: str,
    ) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                """UPDATE demo_sessions SET
                       ended_at=?,state=?,attempted=?,passed=?,failed=?,skipped=?,stopped=?,final_reason=?
                   WHERE session_id=?""",
                (
                    ended_at,
                    state,
                    counters["attempted"],
                    counters["passed"],
                    counters["failed"],
                    counters["skipped"],
                    counters["stopped"],
                    final_reason,
                    session_id,
                ),
            )

    def history(self, limit: int = 50) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(500, int(limit)))
        with closing(self._connect()) as db:
            sessions = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM demo_sessions ORDER BY started_at DESC LIMIT ?",
                    (bounded_limit,),
                )
            ]
            for session in sessions:
                try:
                    session["configuration"] = json.loads(session.pop("configuration_json"))
                except (TypeError, ValueError, json.JSONDecodeError):
                    session["configuration"] = {}
                    session.pop("configuration_json", None)
                session["samples"] = [
                    dict(row)
                    for row in db.execute(
                        """SELECT sample_id,cycle_no,slot_code,started_at,completed_at,
                                  duration_s,result,reason
                           FROM demo_samples WHERE session_id=? ORDER BY cycle_no""",
                        (session["session_id"],),
                    )
                ]
            return sessions

    def export_sample_rows(self) -> list[tuple[Any, ...]]:
        with closing(self._connect()) as db:
            return [
                tuple(row)
                for row in db.execute(
                    """SELECT session_id,cycle_no,slot_code,started_at,completed_at,
                              duration_s,result,reason
                       FROM demo_samples ORDER BY started_at"""
                )
            ]
