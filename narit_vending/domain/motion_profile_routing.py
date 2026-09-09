"""Fail-closed routing policy for the candidate X/Y S-curve runtime."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from narit_vending.domain.motion_profile import supports_scurve


class ProfileOperation(str, Enum):
    MOVE = "move"
    JOG = "jog"
    HOME = "home"
    LIMIT_SEEK = "limit_seek"


class ProfileAxisConfig(Protocol):
    name: str
    scurve_enabled: bool | None


@dataclass(frozen=True)
class ProfileRouteDecision:
    axis: str
    operation: ProfileOperation
    configured: bool
    capability_ready: bool
    runtime_ready: bool
    route: str
    executable: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "axis": self.axis,
            "operation": self.operation.value,
            "configured": self.configured,
            "capability_ready": self.capability_ready,
            "runtime_ready": self.runtime_ready,
            "route": self.route,
            "executable": self.executable,
            "reason": self.reason,
        }


def decide_profile_route(
    config: ProfileAxisConfig,
    operation: ProfileOperation | str,
    *,
    capability_ready: bool,
    runtime_ready: bool,
) -> ProfileRouteDecision:
    """Choose legacy/buffered/blocked without silently downgrading enabled profiles."""

    axis = str(config.name).lower()
    selected_operation = ProfileOperation(operation)
    configured = bool(config.scurve_enabled)
    if not supports_scurve(axis):
        return ProfileRouteDecision(
            axis, selected_operation, False, capability_ready, runtime_ready,
            "legacy", True, "Z remains on the existing motion path",
        )
    if not configured:
        return ProfileRouteDecision(
            axis, selected_operation, False, capability_ready, runtime_ready,
            "legacy", True, "S-curve is disabled in effective configuration",
        )
    if not capability_ready:
        return ProfileRouteDecision(
            axis, selected_operation, True, False, runtime_ready,
            "blocked", False, "NUCLEO handshake does not advertise buffered S-curve support",
        )
    if selected_operation in (ProfileOperation.HOME, ProfileOperation.LIMIT_SEEK):
        return ProfileRouteDecision(
            axis, selected_operation, True, True, runtime_ready,
            "blocked", False, "Sensor-terminated S-curve protocol is not implemented",
        )
    if not runtime_ready:
        return ProfileRouteDecision(
            axis, selected_operation, True, True, False,
            "blocked", False, "Buffered S-curve runtime is not connected to production transport",
        )
    return ProfileRouteDecision(
        axis, selected_operation, True, True, True,
        "buffered_scurve", True, "Buffered X/Y profile route is available",
    )
