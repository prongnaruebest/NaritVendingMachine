from __future__ import annotations

import hashlib
import pytest

from narit_vending.domain.motion_profile import MotionProfileLimits, build_seven_segment_scurve
from narit_vending.domain.nucleo_profile_protocol import (
    PROFILE_CAPABILITIES,
    SENSOR_TERMINATED_PROFILE_CAPABILITIES,
    BufferedProfileCommand,
    NucleoCapabilities,
    SensorTerminatedProfileCommand,
    validate_profile_sequence,
)
from narit_vending.nucleo import NucleoLink


def _command(*, axis: str = "x", sequence: int = 0, command_id: str = "move-1") -> BufferedProfileCommand:
    profile = build_seven_segment_scurve(100.0, MotionProfileLimits(30.0, 20.0, 100.0))
    return BufferedProfileCommand.from_profile(
        command_id=command_id,
        axis=axis,
        direction=1,
        steps=6471,
        sequence=sequence,
        profile=profile,
    )


def test_protocol_v3_never_implies_scurve_support():
    capabilities = NucleoCapabilities.from_handshake(
        {"protocol": 3, "capabilities": sorted(PROFILE_CAPABILITIES)}, fallback_protocol=3
    )
    assert not capabilities.supports_buffered_scurve


def test_protocol_v4_requires_every_explicit_capability():
    incomplete = NucleoCapabilities.from_handshake(
        {"protocol": 4, "capabilities": ["continuous_profile"]}, fallback_protocol=4
    )
    complete = NucleoCapabilities.from_handshake(
        {"protocol": 4, "capabilities": {name: True for name in PROFILE_CAPABILITIES}},
        fallback_protocol=4,
    )
    assert not incomplete.supports_buffered_scurve
    assert complete.supports_buffered_scurve


def test_z_profile_is_rejected_by_contract():
    with pytest.raises(ValueError, match="X/Y only"):
        _command(axis="z")


def test_payload_is_stable_and_checksummed():
    first = _command().payload()
    second = _command().payload()
    assert first == second
    assert first["axis"] == "X"
    assert len(first["phases"]) == 7
    assert len(first["checksum"]) == 64
    phases = first["phases"]
    assert phases[-1]["end_step"] == 6471
    assert phases[0]["duration_us"] > 0
    assert phases[0]["start_rate_millihz"] == 0
    assert phases[-1]["end_rate_millihz"] == 0


def test_pulse_domain_phases_are_direction_independent_but_direction_remains_explicit():
    limits = MotionProfileLimits(30.0, 20.0, 100.0)
    forward = BufferedProfileCommand.from_profile(
        command_id="forward", axis="x", direction=1, steps=6471, sequence=0,
        profile=build_seven_segment_scurve(100.0, limits),
    )
    reverse = BufferedProfileCommand.from_profile(
        command_id="reverse", axis="x", direction=0, steps=6471, sequence=0,
        profile=build_seven_segment_scurve(-100.0, limits),
    )
    assert forward.phases == reverse.phases
    assert forward.direction == 1
    assert reverse.direction == 0


def test_sequence_rejects_duplicate_gap_and_cross_command_frames():
    assert len(validate_profile_sequence([_command(sequence=0), _command(sequence=1)])) == 2
    with pytest.raises(ValueError, match="contiguous"):
        validate_profile_sequence([_command(sequence=1)])
    with pytest.raises(ValueError, match="one command_id"):
        validate_profile_sequence([_command(sequence=0), _command(sequence=1, command_id="move-2")])


def test_link_status_exposes_capability_without_sending_profile():
    link = NucleoLink({"protocol_version": 4})
    link._last_payload = {"protocol": 4, "capabilities": sorted(PROFILE_CAPABILITIES)}
    status = link.status_payload()
    assert status["supports_buffered_scurve"] is True
    assert set(status["capabilities"]) == PROFILE_CAPABILITIES
    assert status["supports_sensor_terminated_scurve"] is False


def test_sensor_terminated_profile_requires_explicit_additional_capabilities():
    buffered_only = NucleoCapabilities(4, PROFILE_CAPABILITIES)
    complete = NucleoCapabilities(4, PROFILE_CAPABILITIES | SENSOR_TERMINATED_PROFILE_CAPABILITIES)

    assert not buffered_only.supports_sensor_terminated_scurve
    assert complete.supports_sensor_terminated_scurve


def test_sensor_profile_payload_is_axis_scoped_checksummed_and_watchdog_bounded():
    command = SensorTerminatedProfileCommand(
        profile=_command(axis="x"),
        sensor="X_MAX",
        stop_mode="controlled",
        watchdog_us=60_000_000,
    )

    payload = command.payload()

    assert payload["type"] == "sensor_profile"
    assert payload["termination_sensor"] == "X_MAX"
    assert payload["sensor_stop_mode"] == "controlled"
    assert payload["watchdog_us"] == 60_000_000
    assert len(payload["checksum"]) == 64

    wire = command.wire_line()
    fields = wire.split(" ")
    assert fields[:9] == [
        "SENSOR_PROFILE", "move-1", "X", "1", "6471", "0",
        "X_MAX", "controlled", "60000000",
    ]
    assert fields[9] == hashlib.sha256(" ".join([*fields[:9], *fields[10:]]).encode("ascii")).hexdigest()
    assert len(fields) == 59
    assert wire.isascii() and "\n" not in wire


def test_buffered_profile_wire_line_matches_candidate_parser_order():
    command = _command()
    fields = command.wire_line().split(" ")
    assert fields[:6] == ["PROFILE", "move-1", "X", "1", "6471", "0"]
    assert fields[6] == hashlib.sha256(" ".join([*fields[:6], *fields[7:]]).encode("ascii")).hexdigest()
    assert len(fields) == 56


@pytest.mark.parametrize(
    ("sensor", "stop_mode", "watchdog", "message"),
    [
        ("Y_MIN", "controlled", 1_000_000, "sensor must match"),
        ("X_MIN", "coast", 1_000_000, "stop_mode"),
        ("X_MIN", "immediate", 10_000, "watchdog_us"),
    ],
)
def test_sensor_profile_rejects_cross_axis_mode_and_watchdog_errors(sensor, stop_mode, watchdog, message):
    with pytest.raises(ValueError, match=message):
        SensorTerminatedProfileCommand(
            profile=_command(axis="x"),
            sensor=sensor,
            stop_mode=stop_mode,
            watchdog_us=watchdog,
        )
