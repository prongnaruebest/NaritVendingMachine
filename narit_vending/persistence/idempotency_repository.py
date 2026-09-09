"""Repositories for bounded command idempotency results."""

from __future__ import annotations

import json
import sqlite3
from collections import OrderedDict
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .sqlite_migrations import Migration, SQLiteMigrator


@dataclass(frozen=True)
class IdempotencyRecord:
    key: str
    fingerprint: str
    result: dict[str, Any]


class IdempotencyRepository(Protocol):
    def get(self, key: str) -> IdempotencyRecord | None: ...
    def put(self, record: IdempotencyRecord) -> None: ...


class InMemoryIdempotencyRepository:
    def __init__(self, capacity: int = 256) -> None:
        self.capacity = max(1, int(capacity))
        self._records: OrderedDict[str, IdempotencyRecord] = OrderedDict()

    def get(self, key: str) -> IdempotencyRecord | None:
        record = self._records.get(key)
        if record is not None:
            self._records.move_to_end(key)
        return record

    def put(self, record: IdempotencyRecord) -> None:
        self._records[record.key] = record
        self._records.move_to_end(record.key)
        while len(self._records) > self.capacity:
            self._records.popitem(last=False)


IDEMPOTENCY_MIGRATIONS = (
    Migration(
        1,
        "create_command_idempotency",
        (
            """CREATE TABLE IF NOT EXISTS command_idempotency (
                 idempotency_key TEXT PRIMARY KEY,
                 fingerprint TEXT NOT NULL,
                 result_json TEXT NOT NULL,
                 created_at TEXT NOT NULL,
                 last_accessed_at TEXT NOT NULL
               )""",
            "CREATE INDEX IF NOT EXISTS idx_command_idempotency_accessed ON command_idempotency(last_accessed_at)",
        ),
    ),
)


class SQLiteIdempotencyRepository:
    def __init__(self, database_path: str | Path, capacity: int = 256) -> None:
        self.database_path = Path(database_path)
        self.capacity = max(1, int(capacity))
        self.schema_version = SQLiteMigrator(self.database_path, IDEMPOTENCY_MIGRATIONS).migrate()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="microseconds")

    def get(self, key: str) -> IdempotencyRecord | None:
        with closing(self._connect()) as db, db:
            row = db.execute(
                "SELECT fingerprint,result_json FROM command_idempotency WHERE idempotency_key=?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            db.execute(
                "UPDATE command_idempotency SET last_accessed_at=? WHERE idempotency_key=?",
                (self._now(), key),
            )
        return IdempotencyRecord(key, str(row["fingerprint"]), json.loads(row["result_json"]))

    def put(self, record: IdempotencyRecord) -> None:
        now = self._now()
        with closing(self._connect()) as db, db:
            db.execute(
                """INSERT INTO command_idempotency(
                       idempotency_key,fingerprint,result_json,created_at,last_accessed_at
                   ) VALUES(?,?,?,?,?)
                   ON CONFLICT(idempotency_key) DO UPDATE SET
                     fingerprint=excluded.fingerprint,
                     result_json=excluded.result_json,
                     last_accessed_at=excluded.last_accessed_at""",
                (record.key, record.fingerprint, json.dumps(record.result, sort_keys=True), now, now),
            )
            db.execute(
                """DELETE FROM command_idempotency WHERE idempotency_key IN (
                       SELECT idempotency_key FROM command_idempotency
                       ORDER BY last_accessed_at DESC LIMIT -1 OFFSET ?
                   )""",
                (self.capacity,),
            )
