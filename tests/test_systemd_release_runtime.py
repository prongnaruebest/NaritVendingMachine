from __future__ import annotations

from pathlib import Path

import pytest

from narit_vending.systemd_release_runtime import SystemdReleaseRuntime


def _runtime(tmp_path: Path, *, codes: list[int], health: list[bool] | None = None):
    commands: list[tuple[str, ...]] = []
    switches: list[tuple[Path, Path]] = []
    health_results = list(health or [True])
    sleeps: list[float] = []

    def run(command):
        commands.append(tuple(command))
        return codes.pop(0)

    def probe(_url, _timeout):
        return health_results.pop(0)

    runtime = SystemdReleaseRuntime(
        current_link=tmp_path / "current",
        controller_service="controller.service",
        web_service="web.service",
        live_url="http://127.0.0.1/health/live",
        validator=lambda _path: None,
        command_runner=run,
        health_probe=probe,
        current_switcher=lambda current, release: switches.append((current, release)),
        sleeper=sleeps.append,
        health_attempts=len(health_results),
    )
    return runtime, commands, switches, sleeps


def test_start_switches_release_before_starting_services(tmp_path: Path):
    runtime, commands, switches, _ = _runtime(tmp_path, codes=[0])
    candidate = tmp_path / "candidate"

    runtime.start(candidate)

    assert switches == [(tmp_path / "current", candidate)]
    assert commands == [("systemctl", "start", "controller.service", "web.service")]


def test_stop_orders_web_before_controller(tmp_path: Path):
    runtime, commands, _, _ = _runtime(tmp_path, codes=[0])

    runtime.stop()

    assert commands == [("systemctl", "stop", "web.service", "controller.service")]


def test_health_requires_both_services_before_http_probe(tmp_path: Path):
    runtime, commands, _, sleeps = _runtime(tmp_path, codes=[0, 0], health=[False, True])

    assert runtime.healthy() is True
    assert commands == [
        ("systemctl", "is-active", "--quiet", "controller.service"),
        ("systemctl", "is-active", "--quiet", "web.service"),
    ]
    assert sleeps == [1.0]


def test_health_does_not_probe_http_when_service_is_inactive(tmp_path: Path):
    runtime, commands, _, sleeps = _runtime(tmp_path, codes=[1], health=[True])

    assert runtime.healthy() is False
    assert commands == [("systemctl", "is-active", "--quiet", "controller.service")]
    assert sleeps == []


def test_command_failure_is_not_reported_as_success(tmp_path: Path):
    runtime, _, _, _ = _runtime(tmp_path, codes=[1])

    with pytest.raises(RuntimeError, match="Command failed"):
        runtime.stop()
