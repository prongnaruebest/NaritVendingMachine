"""Small transactional SQLite schema migration framework."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.version <= 0:
            raise ValueError("migration version must be greater than zero")
        if not self.name.strip():
            raise ValueError("migration name cannot be empty")
        if not self.statements:
            raise ValueError("migration must contain at least one SQL statement")


class SQLiteMigrator:
    """Apply each registered migration once and retain an audit row."""

    def __init__(self, database_path: str | Path, migrations: Iterable[Migration]) -> None:
        self.database_path = Path(database_path)
        self.migrations = tuple(sorted(migrations, key=lambda item: item.version))
        versions = [migration.version for migration in self.migrations]
        if len(versions) != len(set(versions)):
            raise ValueError("migration versions must be unique")

    def migrate(self) -> int:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.database_path, timeout=5)) as db:
            db.execute("PRAGMA foreign_keys = ON")
            db.execute(
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                       version INTEGER PRIMARY KEY,
                       name TEXT NOT NULL,
                       applied_at TEXT NOT NULL
                   )"""
            )
            applied = {
                int(row[0]): str(row[1])
                for row in db.execute("SELECT version, name FROM schema_migrations")
            }
            for migration in self.migrations:
                if migration.version in applied:
                    if applied[migration.version] != migration.name:
                        raise RuntimeError(
                            f"migration {migration.version} name mismatch: "
                            f"database={applied[migration.version]!r}, code={migration.name!r}"
                        )
                    continue
                with db:
                    for statement in migration.statements:
                        db.execute(statement)
                    db.execute(
                        "INSERT INTO schema_migrations(version,name,applied_at) VALUES(?,?,?)",
                        (migration.version, migration.name, datetime.now(timezone.utc).isoformat()),
                    )
            return max((migration.version for migration in self.migrations), default=0)

    def current_version(self) -> int:
        if not self.database_path.exists():
            return 0
        with closing(sqlite3.connect(self.database_path, timeout=5)) as db:
            table = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            ).fetchone()
            if table is None:
                return 0
            row = db.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()
            return int(row[0]) if row else 0
