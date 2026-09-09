from __future__ import annotations

import pytest

from narit_vending.domain.errors import NucleoError
from narit_vending.domain.motion_profile import MotionProfileLimits, build_seven_segment_scurve
from narit_vending.domain.nucleo_profile_protocol import (
    PROFILE_CAPABILITIES,
    BufferedProfileCommand,
    NucleoCapabilities,
)
from narit_vending.nucleo_profile_transport import BufferedProfileTransport


def _capabilities(protocol: int = 4, complete: bool = True) -> NucleoCapabilities:
    advertised = PROFILE_CAPABILITIES if complete else frozenset({"continuous_profile"})
    return NucleoCapabilities(protocol, frozenset(advertised))


def _commands(count: int = 2) -> list[BufferedProfileCommand]:
    profile = build_seven_segment_scurve(100, MotionProfileLimits(30, 20, 100))
    return [
        BufferedProfileCommand.from_profile(
            command_id="move-xy-1",
            axis="x",
            direction=1,
            steps=6471,
            sequence=index,
            profile=profile,
        )
        for index in range(count)
    ]


def test_transport_is_disabled_by_default_and_performs_no_exchange():
    calls = []
    transport = BufferedProfileTransport(exchange=lambda payload, timeout: calls.append(payload), capabilities=_capabilities())
    with pytest.raises(NucleoError, match="disabled"):
        transport.stage(_commands())
    assert calls == []


def test_incomplete_or_v3_capability_rejects_before_exchange():
    for capabilities in (_capabilities(protocol=3), _capabilities(complete=False)):
        transport = BufferedProfileTransport(exchange=lambda payload, timeout: None, capabilities=capabilities, enabled=True)
        with pytest.raises(NucleoError, match="does not advertise"):
            transport.stage(_commands())


def test_stage_correlates_every_ack_then_start_is_separate():
    calls = []

    def exchange(payload, timeout):
        calls.append(payload)
        if payload["type"] == "profile_start":
            return {"type": "ack", "command_id": payload["command_id"], "status": "running"}
        return {
            "type": "ack",
            "command_id": payload["command_id"],
            "sequence": payload["sequence"],
            "status": "buffered",
        }

    transport = BufferedProfileTransport(exchange=exchange, capabilities=_capabilities(), enabled=True)
    staged = transport.stage(_commands())
    assert staged == {"ok": True, "command_id": "move-xy-1", "frames": 2, "started": False}
    assert all(call["type"] == "profile" for call in calls)
    assert transport.start("move-xy-1")["status"] == "running"
    assert calls[-1]["type"] == "profile_start"


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (None, "timed out"),
        ({"type": "ack", "command_id": "wrong", "sequence": 0, "status": "buffered"}, "command_id mismatch"),
        ({"type": "ack", "command_id": "move-xy-1", "sequence": 4, "status": "buffered"}, "sequence mismatch"),
        ({"type": "error", "code": "OUT_OF_ORDER", "error": "expected 0"}, "OUT_OF_ORDER"),
    ],
)
def test_invalid_ack_timeout_and_firmware_errors_clear_staged_state(response, message):
    transport = BufferedProfileTransport(exchange=lambda payload, timeout: response, capabilities=_capabilities(), enabled=True)
    with pytest.raises(NucleoError, match=message):
        transport.stage(_commands(1))
    assert transport.status.staged_command_id is None
    assert transport.status.staged_frames == 0


def test_duplicate_ack_is_idempotent_but_start_requires_complete_stage():
    def exchange(payload, timeout):
        return {"type": "ack", "command_id": payload["command_id"], "sequence": payload["sequence"], "status": "duplicate"}

    transport = BufferedProfileTransport(exchange=exchange, capabilities=_capabilities(), enabled=True)
    transport.stage(_commands(1))
    assert transport.status.staged_frames == 1
    with pytest.raises(NucleoError, match="not fully staged"):
        transport.start("another-command")


def test_buffer_underrun_is_a_hard_transport_error():
    transport = BufferedProfileTransport(exchange=lambda payload, timeout: None, capabilities=_capabilities(), enabled=True)
    transport._staged_command_id = "move-xy-1"
    with pytest.raises(NucleoError, match="buffer underrun"):
        transport.accept_telemetry({"command_id": "move-xy-1", "state": "BUFFER_UNDERRUN"})
    assert "underrun" in transport.status.last_error


def test_transport_payload_contains_only_integer_pulse_domain_kinematics():
    captured = []

    def exchange(payload, timeout):
        captured.append(payload)
        return {"type": "ack", "command_id": payload["command_id"], "sequence": payload["sequence"], "status": "buffered"}

    transport = BufferedProfileTransport(exchange=exchange, capabilities=_capabilities(), enabled=True)
    transport.stage(_commands(1))
    phase = captured[0]["phases"][0]
    assert "jerk_mm_s3" not in phase
    assert all(isinstance(phase[name], int) for name in (
        "duration_us", "end_step", "start_rate_millihz", "end_rate_millihz",
        "start_accel_millihz_s", "end_accel_millihz_s", "jerk_millihz_s2",
    ))
