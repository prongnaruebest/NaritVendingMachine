from __future__ import annotations

from pathlib import Path

import pytest

from narit_vending.release_lifecycle import (
    ReleaseActivationError,
    ReleaseActivator,
    ReleaseState,
    ReleaseStateStore,
    ReleaseStatus,
)


OLD = "111111111111-222222222222"
NEW = "333333333333-444444444444"


class FakeRuntime:
    def __init__(self, health_results: list[bool] | None = None, validation_error: Exception | None = None):
        self.health_results = list(health_results or [True])
        self.validation_error = validation_error
        self.calls: list[str] = []

    def validate(self, release_dir: Path) -> None:
        self.calls.append(f"validate:{release_dir.name}")
        if self.validation_error:
            raise self.validation_error

    def stop(self) -> None:
        self.calls.append("stop")

    def start(self, release_dir: Path) -> None:
        self.calls.append(f"start:{release_dir.name}")

    def healthy(self) -> bool:
        self.calls.append("healthy")
        return self.health_results.pop(0)


def _activator(tmp_path: Path, runtime: FakeRuntime):
    releases = tmp_path / "releases"
    (releases / OLD).mkdir(parents=True)
    (releases / NEW).mkdir()
    store = ReleaseStateStore(tmp_path / "state" / "release-state.json")
    store.write(ReleaseState(status=ReleaseStatus.HEALTHY, active_release=OLD))
    return ReleaseActivator(releases, store, runtime), store


def test_activation_validates_before_stopping_and_records_healthy_candidate(tmp_path: Path):
    runtime = FakeRuntime([True])
    activator, store = _activator(tmp_path, runtime)

    result = activator.activate(NEW)

    assert result.status == ReleaseStatus.HEALTHY
    assert result.active_release == NEW
    assert result.previous_release == OLD
    assert runtime.calls == [f"validate:{NEW}", "stop", f"start:{NEW}", "healthy"]
    assert store.read() == result


def test_validation_failure_does_not_stop_running_release(tmp_path: Path):
    runtime = FakeRuntime(validation_error=ValueError("invalid candidate"))
    activator, store = _activator(tmp_path, runtime)

    with pytest.raises(ValueError, match="invalid candidate"):
        activator.activate(NEW)

    assert runtime.calls == [f"validate:{NEW}"]
    assert store.read().active_release == OLD


def test_failed_candidate_rolls_back_and_rechecks_previous_health(tmp_path: Path):
    runtime = FakeRuntime([False, True])
    activator, store = _activator(tmp_path, runtime)

    result = activator.activate(NEW)

    assert result.status == ReleaseStatus.ROLLED_BACK
    assert result.active_release == OLD
    assert runtime.calls == [
        f"validate:{NEW}",
        "stop",
        f"start:{NEW}",
        "healthy",
        "stop",
        f"start:{OLD}",
        "healthy",
    ]
    assert store.read() == result


def test_failed_candidate_and_failed_rollback_leave_explicit_failed_state(tmp_path: Path):
    runtime = FakeRuntime([False, False])
    activator, store = _activator(tmp_path, runtime)

    with pytest.raises(ReleaseActivationError, match="rollback failed"):
        activator.activate(NEW)

    state = store.read()
    assert state.status == ReleaseStatus.FAILED
    assert state.active_release is None


def test_invalid_or_unstaged_release_never_calls_runtime(tmp_path: Path):
    runtime = FakeRuntime()
    activator, _ = _activator(tmp_path, runtime)

    with pytest.raises(ReleaseActivationError, match="Invalid release ID"):
        activator.activate("../../unsafe")
    with pytest.raises(ReleaseActivationError, match="not staged"):
        activator.activate("aaaaaaaaaaaa-bbbbbbbbbbbb")

    assert runtime.calls == []
