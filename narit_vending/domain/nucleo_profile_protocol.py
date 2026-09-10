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
SENSOR_TERMINATED_PROFILE_CAPABILITIES = frozenset(
    {"sensor_terminated_profile", "axis_sensor_stop", "profile_watchdog"}
)
_COMMAND_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")


def _phase_wire_fields(phases: tuple[dict[str, int | str], ...]) -> list[str]:
    names = (
        "duration_us", "end_step", "start_rate_millihz", "end_rate_millihz",
        "start_accel_millihz_s", "end_accel_millihz_s", "jerk_millihz_s2",
    )
    return [str(phase[name]) for phase in phases for name in names]


@dataclass(frozen=True)
class NucleoCapabilities:
    protocol: int
    advertised: frozenset[str]

    @property
    def supports_buffered_scurve(self) -> bool:
        return self.protocol >= PROFILE_PROTOCOL_MIN_VERSION and PROFILE_CAPABILITIES <= self.advertised

    @property
    def supports_sensor_terminated_scurve(self) -> bool:
        return self.supports_buffered_scurve and SENSOR_TERMINATED_PROFILE_CAPABILITIES <= self.advertised

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
    phases: tuple[dict[str, int | str], ...]

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
            required = {
                "duration_us",
                "end_step",
                "start_rate_millihz",
                "end_rate_millihz",
                "start_accel_millihz_s",
                "end_accel_millihz_s",
                "jerk_millihz_s2",
            }
            if not required <= phase.keys():
                raise ValueError("pulse-domain profile phase is incomplete")
            for name in required:
                value = phase[name]
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ValueError(f"phase {name} must be an integer")
            duration_us = phase["duration_us"]
            end_step = phase["end_step"]
            if not isinstance(duration_us, int) or not isinstance(end_step, int):
                raise ValueError("phase duration_us and end_step must be integers")
            if duration_us < 0 or end_step < 0:
                raise ValueError("phase duration_us and end_step must be non-negative")

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
        if steps <= 0 or profile.distance_mm == 0:
            raise ValueError("non-zero profile distance and steps are required")
        pulses_per_mm = steps / abs(profile.distance_mm)
        direction_sign = math.copysign(1.0, profile.distance_mm)
        elapsed = 0.0
        pulse_phases: list[dict[str, int | str]] = []
        for index, phase in enumerate(profile.phases):
            start = profile.sample(elapsed)
            elapsed += phase.duration_s
            end = profile.sample(elapsed)
            end_step = steps if index == len(profile.phases) - 1 else round(abs(end.position_mm) * pulses_per_mm)
            pulse_phases.append(
                {
                    "name": phase.name,
                    "duration_us": round(phase.duration_s * 1_000_000),
                    "end_step": end_step,
                    "start_rate_millihz": round(abs(start.velocity_mm_s) * pulses_per_mm * 1000),
                    "end_rate_millihz": round(abs(end.velocity_mm_s) * pulses_per_mm * 1000),
                    "start_accel_millihz_s": round(start.acceleration_mm_s2 * direction_sign * pulses_per_mm * 1000),
                    "end_accel_millihz_s": round(end.acceleration_mm_s2 * direction_sign * pulses_per_mm * 1000),
                    "jerk_millihz_s2": round(phase.jerk_mm_s3 * direction_sign * pulses_per_mm * 1000),
                }
            )
        return cls(
            command_id=command_id,
            axis=axis.lower(),
            direction=direction,
            steps=steps,
            sequence=sequence,
            phases=tuple(pulse_phases),
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

    def wire_line(self) -> str:
        """Return the stable ASCII frame consumed by the candidate C parser."""

        payload = self.payload()
        fields = [
            "PROFILE", self.command_id, self.axis.upper(), str(self.direction),
            str(self.steps), str(self.sequence), str(payload["checksum"]),
            *_phase_wire_fields(self.phases),
        ]
        return " ".join(fields)


@dataclass(frozen=True)
class SensorTerminatedProfileCommand:
    """Profile envelope whose endpoint is a physical X/Y limit sensor."""

    profile: BufferedProfileCommand
    sensor: str
    stop_mode: str
    watchdog_us: int

    def __post_init__(self) -> None:
        expected = {"X_MIN", "X_MAX"} if self.profile.axis == "x" else {"Y_MIN", "Y_MAX"}
        if self.sensor not in expected:
            raise ValueError(f"sensor must match profile axis ({'/'.join(sorted(expected))})")
        if self.stop_mode not in {"controlled", "immediate"}:
            raise ValueError("stop_mode must be controlled or immediate")
        if isinstance(self.watchdog_us, bool) or not 100_000 <= self.watchdog_us <= 3_600_000_000:
            raise ValueError("watchdog_us must be within 100000-3600000000")
    def payload(self) -> dict[str, object]:
        body = self.profile.payload()
        body.update(
            {
                "type": "sensor_profile",
                "termination_sensor": self.sensor,
                "sensor_stop_mode": self.stop_mode,
                "watchdog_us": self.watchdog_us,
            }
        )
        body.pop("checksum", None)
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        body["checksum"] = hashlib.sha256(canonical.encode("ascii")).hexdigest()
        return body


    def wire_line(self) -> str:
        """Return the stable sensor-terminated ASCII frame for firmware."""

        payload = self.payload()
        profile = self.profile
        fields = [
            "SENSOR_PROFILE", profile.command_id, profile.axis.upper(),
            str(profile.direction), str(profile.steps), str(profile.sequence),
            self.sensor, self.stop_mode, str(self.watchdog_us),
            str(payload["checksum"]), *_phase_wire_fields(profile.phases),
        ]
        return " ".join(fields)


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
