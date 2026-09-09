from __future__ import annotations

import pytest

from narit_vending.domain.motion_profile import MotionProfileLimits, build_seven_segment_scurve
from narit_vending.domain.nucleo_profile_protocol import (
    PROFILE_CAPABILITIES,
    BufferedProfileCommand,
    NucleoCapabilities,
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
