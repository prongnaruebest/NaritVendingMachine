from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol


class MigrationPhase(str, Enum):
    IDLE = "IDLE"
    PREFLIGHT = "PREFLIGHT"
    BACKED_UP = "BACKED_UP"
    QUIESCED = "QUIESCED"
    MIGRATING = "MIGRATING"
    STARTING = "STARTING"
    COMPLETE = "COMPLETE"
    ABORTED = "ABORTED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"


@dataclass(frozen=True)
class MigrationState:
    phase: MigrationPhase = MigrationPhase.IDLE
    release_id: str | None = None
    detail: str = ""


class MigrationRuntime(Protocol):
    def preflight(self, release_id: str) -> None: ...

    def backup(self) -> None: ...

    def stop(self) -> None: ...

    def migrate_layout(self, release_id: str) -> None: ...

    def install_units(self, release_id: str) -> None: ...

    def start(self) -> None: ...

    def healthy(self) -> bool: ...

    def rollback_legacy(self) -> None: ...


class MigrationError(RuntimeError):
    pass


class MigrationStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> MigrationState:
        if not self.path.exists():
            return MigrationState()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return MigrationState(
            phase=MigrationPhase(data.get("phase", MigrationPhase.IDLE.value)),
            release_id=data.get("release_id"),
            detail=str(data.get("detail", "")),
        )

    def write(self, state: MigrationState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        payload = asdict(state)
        payload["phase"] = state.phase.value
        try:
            with temporary.open("x", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary.exists():
                temporary.unlink()


class MigrationCoordinator:
    RECOVERABLE_PHASES = {
        MigrationPhase.QUIESCED,
        MigrationPhase.MIGRATING,
        MigrationPhase.STARTING,
    }

    def __init__(self, store: MigrationStateStore, runtime: MigrationRuntime) -> None:
        self.store = store
        self.runtime = runtime

    def _state(self, phase: MigrationPhase, release_id: str, detail: str) -> MigrationState:
        state = MigrationState(phase=phase, release_id=release_id, detail=detail)
        self.store.write(state)
        return state

    def migrate(self, release_id: str) -> MigrationState:
        existing = self.store.read()
        if existing.phase in self.RECOVERABLE_PHASES:
            raise MigrationError("Interrupted migration must be recovered before starting another")

        self._state(MigrationPhase.PREFLIGHT, release_id, "Validating migration preconditions")
        try:
            self.runtime.preflight(release_id)
            self.runtime.backup()
        except Exception as exc:
            self._state(MigrationPhase.ABORTED, release_id, f"Stopped before service shutdown: {exc}")
            raise MigrationError(str(exc)) from exc

        self._state(MigrationPhase.BACKED_UP, release_id, "Recovery inputs verified")
        try:
            self.runtime.stop()
            self._state(MigrationPhase.QUIESCED, release_id, "Legacy services stopped")
            self._state(MigrationPhase.MIGRATING, release_id, "Creating versioned runtime layout")
            self.runtime.migrate_layout(release_id)
            self.runtime.install_units(release_id)
            self._state(MigrationPhase.STARTING, release_id, "Starting release-layout services")
            self.runtime.start()
            if not self.runtime.healthy():
                raise MigrationError("Release-layout health check failed")
        except Exception as exc:
            return self._rollback(release_id, exc)
        return self._state(MigrationPhase.COMPLETE, release_id, "Migration health check passed")

    def recover_interrupted(self) -> MigrationState:
        state = self.store.read()
        if state.phase not in self.RECOVERABLE_PHASES or state.release_id is None:
            raise MigrationError(f"No interrupted migration to recover (phase={state.phase.value})")
        return self._rollback(state.release_id, MigrationError(f"Interrupted during {state.phase.value}"))

    def _rollback(self, release_id: str, cause: Exception) -> MigrationState:
        try:
            self.runtime.rollback_legacy()
            self.runtime.start()
            if not self.runtime.healthy():
                raise MigrationError("Legacy layout health check failed")
        except Exception as rollback_error:
            failed = self._state(
                MigrationPhase.FAILED,
                release_id,
                f"Migration failed: {cause}; rollback failed: {rollback_error}",
            )
            raise MigrationError(failed.detail) from rollback_error
        return self._state(
            MigrationPhase.ROLLED_BACK,
            release_id,
            f"Legacy layout restored after: {cause}",
        )
