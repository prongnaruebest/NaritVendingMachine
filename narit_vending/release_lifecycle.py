from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol


RELEASE_ID_PATTERN = re.compile(r"^[0-9a-f]{12}-[0-9a-f]{12}$")


class ReleaseStatus(str, Enum):
    IDLE = "IDLE"
    ACTIVATING = "ACTIVATING"
    HEALTHY = "HEALTHY"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ReleaseState:
    status: ReleaseStatus = ReleaseStatus.IDLE
    active_release: str | None = None
    previous_release: str | None = None
    candidate_release: str | None = None
    detail: str = ""


class ReleaseRuntime(Protocol):
    def validate(self, release_dir: Path) -> None: ...

    def stop(self) -> None: ...

    def start(self, release_dir: Path) -> None: ...

    def healthy(self) -> bool: ...


class ReleaseActivationError(RuntimeError):
    pass


class ReleaseStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> ReleaseState:
        if not self.path.exists():
            return ReleaseState()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return ReleaseState(
            status=ReleaseStatus(data.get("status", ReleaseStatus.IDLE.value)),
            active_release=data.get("active_release"),
            previous_release=data.get("previous_release"),
            candidate_release=data.get("candidate_release"),
            detail=str(data.get("detail", "")),
        )

    def write(self, state: ReleaseState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        payload = asdict(state)
        payload["status"] = state.status.value
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


class ReleaseActivator:
    def __init__(self, releases_root: Path, store: ReleaseStateStore, runtime: ReleaseRuntime) -> None:
        self.releases_root = releases_root.resolve()
        self.store = store
        self.runtime = runtime

    def _release_dir(self, release_id: str) -> Path:
        if RELEASE_ID_PATTERN.fullmatch(release_id) is None:
            raise ReleaseActivationError("Invalid release ID")
        release_dir = self.releases_root / release_id
        if not release_dir.is_dir():
            raise ReleaseActivationError(f"Release is not staged: {release_id}")
        return release_dir

    def activate(self, release_id: str) -> ReleaseState:
        candidate = self._release_dir(release_id)
        current = self.store.read()
        if current.active_release == release_id and current.status == ReleaseStatus.HEALTHY:
            return current

        # Validation happens before the running release is touched.
        self.runtime.validate(candidate)
        activating = ReleaseState(
            status=ReleaseStatus.ACTIVATING,
            active_release=current.active_release,
            previous_release=current.active_release,
            candidate_release=release_id,
            detail="Candidate validated; activation in progress",
        )
        self.store.write(activating)

        try:
            self.runtime.stop()
            self.runtime.start(candidate)
            if not self.runtime.healthy():
                raise ReleaseActivationError("Candidate health check failed")
        except Exception as candidate_error:
            return self._rollback(activating, candidate_error)

        healthy = ReleaseState(
            status=ReleaseStatus.HEALTHY,
            active_release=release_id,
            previous_release=activating.previous_release,
            detail="Candidate activated and health check passed",
        )
        self.store.write(healthy)
        return healthy

    def _rollback(self, activating: ReleaseState, candidate_error: Exception) -> ReleaseState:
        previous_id = activating.previous_release
        try:
            self.runtime.stop()
            if previous_id is None:
                raise ReleaseActivationError("No previous release is available")
            previous = self._release_dir(previous_id)
            self.runtime.start(previous)
            if not self.runtime.healthy():
                raise ReleaseActivationError("Previous release health check failed")
        except Exception as rollback_error:
            failed = ReleaseState(
                status=ReleaseStatus.FAILED,
                active_release=None,
                previous_release=previous_id,
                candidate_release=activating.candidate_release,
                detail=f"Candidate failed: {candidate_error}; rollback failed: {rollback_error}",
            )
            self.store.write(failed)
            raise ReleaseActivationError(failed.detail) from rollback_error

        rolled_back = ReleaseState(
            status=ReleaseStatus.ROLLED_BACK,
            active_release=previous_id,
            previous_release=previous_id,
            candidate_release=activating.candidate_release,
            detail=f"Candidate failed and previous release was restored: {candidate_error}",
        )
        self.store.write(rolled_back)
        return rolled_back
