"""Safe integrity, backup, and restore operations for SQLite stores."""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path


class SQLiteIntegrityError(RuntimeError):
    """A database or candidate backup failed SQLite integrity validation."""


class SQLiteMaintenance:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).resolve()

    @staticmethod
    def integrity_check(path: str | Path) -> None:
        candidate = Path(path).resolve()
        if not candidate.is_file():
            raise SQLiteIntegrityError(f"SQLite database does not exist: {candidate}")
        try:
            with closing(sqlite3.connect(f"file:{candidate.as_posix()}?mode=ro", uri=True, timeout=5)) as db:
                rows = [str(row[0]) for row in db.execute("PRAGMA integrity_check")]
        except sqlite3.DatabaseError as exc:
            raise SQLiteIntegrityError(f"SQLite integrity check failed: {exc}") from exc
        if rows != ["ok"]:
            raise SQLiteIntegrityError(f"SQLite integrity check failed: {'; '.join(rows)}")

    def backup_to(self, destination: str | Path) -> Path:
        target = Path(destination).resolve()
        if target == self.database_path:
            raise ValueError("backup destination must differ from the live database")
        self.integrity_check(self.database_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.tmp")
        if temporary.exists():
            temporary.unlink()
        try:
            with closing(sqlite3.connect(self.database_path, timeout=5)) as source, closing(
                sqlite3.connect(temporary, timeout=5)
            ) as backup:
                source.backup(backup)
            self.integrity_check(temporary)
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
        return target

    def restore_from(
        self,
        source_backup: str | Path,
        *,
        safety_backup: str | Path | None = None,
    ) -> None:
        source = Path(source_backup).resolve()
        if source == self.database_path:
            raise ValueError("restore source must differ from the live database")
        self.integrity_check(source)
        if safety_backup is not None and self.database_path.exists():
            self.backup_to(safety_backup)

        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.database_path.with_name(f".{self.database_path.name}.restore.tmp")
        if temporary.exists():
            temporary.unlink()
        try:
            with closing(sqlite3.connect(source, timeout=5)) as backup, closing(
                sqlite3.connect(temporary, timeout=5)
            ) as restored:
                backup.backup(restored)
            self.integrity_check(temporary)
            os.replace(temporary, self.database_path)
        finally:
            if temporary.exists():
                temporary.unlink()
