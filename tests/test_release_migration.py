from __future__ import annotations

from pathlib import Path

import pytest

from narit_vending.release_migration import (
    MigrationCoordinator,
    MigrationError,
    MigrationPhase,
    MigrationStateStore,
)


RELEASE = "aaaaaaaaaaaa-bbbbbbbbbbbb"


class FakeMigrationRuntime:
    def __init__(
        self,
        *,
        fail: str | None = None,
        interrupt: str | None = None,
        rollback_fails: bool = False,
    ) -> None:
        self.fail = fail
        self.interrupt = interrupt
        self.rollback_fails = rollback_fails
        self.rolled_back = False
        self.calls: list[str] = []

    def _call(self, name: str) -> None:
        self.calls.append(name)
        if self.interrupt == name:
            raise KeyboardInterrupt(name)
        if self.fail == name:
            raise RuntimeError(name)

    def preflight(self, release_id: str) -> None:
        self._call(f"preflight:{release_id}")

    def backup(self) -> None:
        self._call("backup")

    def stop(self) -> None:
        self._call("stop")

    def migrate_layout(self, release_id: str) -> None:
        self._call("migrate")

    def install_units(self, release_id: str) -> None:
        self._call("install")

    def start(self) -> None:
        self._call("start")

    def healthy(self) -> bool:
        self._call("healthy")
        return self.fail != "unhealthy" or self.rolled_back

    def rollback_legacy(self) -> None:
        self._call("rollback")
        if self.rollback_fails:
            raise RuntimeError("rollback")
        self.rolled_back = True


def _coordinator(tmp_path: Path, runtime: FakeMigrationRuntime):
    store = MigrationStateStore(tmp_path / "migration-state.json")
    return MigrationCoordinator(store, runtime), store


def test_successful_migration_records_complete_only_after_health(tmp_path: Path):
    runtime = FakeMigrationRuntime()
    coordinator, store = _coordinator(tmp_path, runtime)

    result = coordinator.migrate(RELEASE)

    assert result.phase == MigrationPhase.COMPLETE
    assert runtime.calls[-2:] == ["start", "healthy"]
    assert store.read() == result


def test_preflight_failure_never_stops_services(tmp_path: Path):
    runtime = FakeMigrationRuntime(fail=f"preflight:{RELEASE}")
    coordinator, store = _coordinator(tmp_path, runtime)

    with pytest.raises(MigrationError):
        coordinator.migrate(RELEASE)

    assert runtime.calls == [f"preflight:{RELEASE}"]
    assert store.read().phase == MigrationPhase.ABORTED


def test_health_failure_restores_and_verifies_legacy_layout(tmp_path: Path):
    runtime = FakeMigrationRuntime(fail="unhealthy")
    coordinator, _ = _coordinator(tmp_path, runtime)

    result = coordinator.migrate(RELEASE)

    assert result.phase == MigrationPhase.ROLLED_BACK
    assert runtime.calls[-3:] == ["rollback", "start", "healthy"]


def test_hard_interruption_leaves_recoverable_journal(tmp_path: Path):
    runtime = FakeMigrationRuntime(interrupt="migrate")
    coordinator, store = _coordinator(tmp_path, runtime)

    with pytest.raises(KeyboardInterrupt):
        coordinator.migrate(RELEASE)
    assert store.read().phase == MigrationPhase.MIGRATING

    runtime.interrupt = None
    result = coordinator.recover_interrupted()

    assert result.phase == MigrationPhase.ROLLED_BACK
    assert runtime.calls[-3:] == ["rollback", "start", "healthy"]


def test_failed_rollback_is_never_reported_as_recovered(tmp_path: Path):
    runtime = FakeMigrationRuntime(fail="unhealthy", rollback_fails=True)
    coordinator, store = _coordinator(tmp_path, runtime)

    with pytest.raises(MigrationError, match="rollback failed"):
        coordinator.migrate(RELEASE)

    assert store.read().phase == MigrationPhase.FAILED
