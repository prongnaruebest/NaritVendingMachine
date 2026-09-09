"""Bounded in-memory and durable SQLite audit repositories."""

from __future__ import annotations

import json
import sqlite3
from collections import deque
from contextlib import closing
from pathlib import Path
from typing import Protocol

from ..domain.audit import AuditEvent
from .sqlite_migrations import Migration, SQLiteMigrator


class AuditRepository(Protocol):
    def append(self, event: AuditEvent) -> None: ...
    def recent(self, limit: int = 100) -> list[AuditEvent]: ...


class InMemoryAuditRepository:
    def __init__(self, capacity: int = 1000) -> None:
        self._events: deque[AuditEvent] = deque(maxlen=max(1, int(capacity)))

    def append(self, event: AuditEvent) -> None:
        self._events.append(event)

    def recent(self, limit: int = 100) -> list[AuditEvent]:
        return list(reversed(self._events))[: max(1, int(limit))]


AUDIT_MIGRATIONS = (
    Migration(
        2,
        "create_command_audit_events",
        (
            """CREATE TABLE IF NOT EXISTS command_audit_events (
                 event_id TEXT PRIMARY KEY,
                 occurred_at TEXT NOT NULL,
                 event_code TEXT NOT NULL,
                 correlation_id TEXT NOT NULL,
                 command_id TEXT NOT NULL,
                 category TEXT NOT NULL,
                 severity TEXT NOT NULL,
                 outcome TEXT NOT NULL,
                 source TEXT NOT NULL,
                 message TEXT NOT NULL,
                 details_json TEXT NOT NULL
               )""",
            "CREATE INDEX IF NOT EXISTS idx_audit_occurred ON command_audit_events(occurred_at)",
            "CREATE INDEX IF NOT EXISTS idx_audit_correlation ON command_audit_events(correlation_id)",
        ),
    ),
)


class SQLiteAuditRepository:
    def __init__(self, database_path: str | Path, capacity: int = 10_000) -> None:
        self.database_path = Path(database_path)
        self.capacity = max(1, int(capacity))
        self.schema_version = SQLiteMigrator(self.database_path, AUDIT_MIGRATIONS).migrate()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def append(self, event: AuditEvent) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO command_audit_events VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    event.event_id, event.occurred_at, event.event_code, event.correlation_id,
                    event.command_id, event.category, event.severity, event.outcome,
                    event.source, event.message, json.dumps(event.details, sort_keys=True, default=str),
                ),
            )
            db.execute(
                """DELETE FROM command_audit_events WHERE event_id IN (
                       SELECT event_id FROM command_audit_events
                       ORDER BY occurred_at DESC, rowid DESC LIMIT -1 OFFSET ?
                   )""",
                (self.capacity,),
            )

    def recent(self, limit: int = 100) -> list[AuditEvent]:
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT * FROM command_audit_events
                   ORDER BY occurred_at DESC, rowid DESC LIMIT ?""",
                (max(1, min(self.capacity, int(limit))),),
            )
            return [
                AuditEvent(
                    event_id=row["event_id"], occurred_at=row["occurred_at"],
                    event_code=row["event_code"], correlation_id=row["correlation_id"],
                    command_id=row["command_id"], category=row["category"],
                    severity=row["severity"], outcome=row["outcome"], source=row["source"],
                    message=row["message"], details=json.loads(row["details_json"]),
                )
                for row in rows
            ]
