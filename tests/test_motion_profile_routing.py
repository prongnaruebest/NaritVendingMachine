from types import SimpleNamespace

import pytest

from narit_vending.domain.motion_profile_routing import ProfileOperation, decide_profile_route


def config(axis: str, enabled: bool | None):
    return SimpleNamespace(name=axis, scurve_enabled=enabled)


@pytest.mark.parametrize("operation", list(ProfileOperation))
def test_disabled_xy_uses_existing_route(operation):
    decision = decide_profile_route(config("x", False), operation, capability_ready=False, runtime_ready=False)

    assert decision.executable
    assert decision.route == "legacy"


@pytest.mark.parametrize("operation", list(ProfileOperation))
def test_z_always_remains_on_existing_route(operation):
    decision = decide_profile_route(config("z", None), operation, capability_ready=True, runtime_ready=True)

    assert decision.executable
    assert decision.route == "legacy"


def test_enabled_xy_fails_closed_when_capability_disappears():
    decision = decide_profile_route(config("y", True), ProfileOperation.MOVE, capability_ready=False, runtime_ready=True)

    assert not decision.executable
    assert decision.route == "blocked"
    assert "handshake" in decision.reason


@pytest.mark.parametrize("operation", [ProfileOperation.HOME, ProfileOperation.LIMIT_SEEK])
def test_sensor_terminated_operations_are_not_misrouted_to_bounded_profile(operation):
    decision = decide_profile_route(config("x", True), operation, capability_ready=True, runtime_ready=True)

    assert not decision.executable
    assert "Sensor-terminated" in decision.reason


@pytest.mark.parametrize("operation", [ProfileOperation.MOVE, ProfileOperation.JOG])
def test_bounded_xy_profile_requires_connected_runtime(operation):
    disconnected = decide_profile_route(config("x", True), operation, capability_ready=True, runtime_ready=False)
    connected = decide_profile_route(config("x", True), operation, capability_ready=True, runtime_ready=True)

    assert not disconnected.executable
    assert connected.executable
    assert connected.route == "buffered_scurve"

