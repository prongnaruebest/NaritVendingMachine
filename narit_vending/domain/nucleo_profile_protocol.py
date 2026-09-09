"""Pure contract for capability-gated NUCLEO buffered X/Y profiles."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Iterable, Mapping

from narit_vending.domain.motion_profile import SevenSegmentSCurve, supports_scurve


PROFILE_PROTOCOL_MIN_VERSION = 4
PROFILE_CAPABILITIES = frozenset(
    {
        "continuous_profile",
        "seven_segment_s_curve",
        "buffered_segments",
        "profile_sequence",
        "profile_telemetry",
    }
)
_COMMAND_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")


@dataclass(frozen=True)
class NucleoCapabilities:
    protocol: int
    advertised: frozenset[str]

    @property
    def supports_buffered_scurve(self) -> bool:
        return self.protocol >= PROFILE_PROTOCOL_MIN_VERSION and PROFILE_CAPABILITIES <= self.advertised

    @classmethod
    def from_handshake(cls, payload: Mapping[str, Any], *, fallback_protocol: int) -> "NucleoCapabilities":
        try:
            protocol = int(payload.get("protocol", fallback_protocol))
        except (TypeError, ValueError):
            protocol = fallback_protocol
        raw = payload.get("capabilities", ())
        if isinstance(raw, Mapping):
            advertised = frozenset(str(name) for name, enabled in raw.items() if enabled is True)
        elif isinstance(raw, (list, tuple, set, frozenset)):
            advertised = frozenset(str(name) for name in raw if isinstance(name, str))
        else:
            advertised = frozenset()
        return cls(protocol=protocol, advertised=advertised)


@dataclass(frozen=True)
class BufferedProfileCommand:
    command_id: str
    axis: str
    direction: int
    steps: int
    sequence: int
    phases: tuple[dict[str, float | str], ...]

    def __post_init__(self) -> None:
        if not _COMMAND_ID_PATTERN.fullmatch(self.command_id):
            raise ValueError("command_id must contain 1-64 safe ASCII identifier characters")
        if not supports_scurve(self.axis):
            raise ValueError("buffered S-curve is commissioned for X/Y only")
        if self.direction not in (0, 1):
            raise ValueError("direction must be 0 or 1")
        if isinstance(self.steps, bool) or self.steps <= 0:
            raise ValueError("steps must be greater than 0")
        if isinstance(self.sequence, bool) or self.sequence < 0:
            raise ValueError("sequence must be greater than or equal to 0")
        if len(self.phases) != 7:
            raise ValueError("seven-segment profile must contain exactly 7 phases")
        for phase in self.phases:
            duration = phase.get("duration_s")
            jerk = phase.get("jerk_mm_s3")
            if not isinstance(duration, (int, float)) or not math.isfinite(float(duration)) or duration < 0:
                raise ValueError("phase duration_s must be finite and non-negative")
            if not isinstance(jerk, (int, float)) or not math.isfinite(float(jerk)):
                raise ValueError("phase jerk_mm_s3 must be finite")

    @classmethod
    def from_profile(
        cls,
        *,
        command_id: str,
        axis: str,
        direction: int,
        steps: int,
        sequence: int,
        profile: SevenSegmentSCurve,
    ) -> "BufferedProfileCommand":
        return cls(
            command_id=command_id,
            axis=axis.lower(),
            direction=direction,
            steps=steps,
            sequence=sequence,
            phases=tuple(phase.to_dict() for phase in profile.phases),
        )

    def payload(self) -> dict[str, object]:
        body: dict[str, object] = {
            "type": "profile",
            "profile_type": "seven_segment_s_curve",
            "command_id": self.command_id,
            "axis": self.axis.upper(),
            "direction": self.direction,
            "steps": self.steps,
            "sequence": self.sequence,
            "phases": list(self.phases),
        }
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        body["checksum"] = hashlib.sha256(canonical.encode("ascii")).hexdigest()
        return body


def validate_profile_sequence(commands: Iterable[BufferedProfileCommand]) -> tuple[BufferedProfileCommand, ...]:
    sequence = tuple(commands)
    if not sequence:
        raise ValueError("profile sequence cannot be empty")
    command_ids = {command.command_id for command in sequence}
    if len(command_ids) != 1:
        raise ValueError("all buffered profiles must share one command_id")
    expected = list(range(len(sequence)))
    actual = [command.sequence for command in sequence]
    if actual != expected:
        raise ValueError("profile sequence must be contiguous, ordered, and start at 0")
    return sequence
