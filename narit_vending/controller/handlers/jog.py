"""Jog command handler."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from narit_vending.shared.commands import CommandEnvelope, CommandResult

_log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_jog_handler(motion_service: Any):
    from narit_vending.shared.commands import CommandResult

    def handle(envelope: "CommandEnvelope") -> "CommandResult":
        params = envelope.parameters
        axis = str(params.get("axis", "")).lower()
        if axis not in ("x", "y", "z"):
            return CommandResult.rejected(envelope.command_id, f"Invalid axis: {axis!r}")
        try:
            distance_mm = float(params["distance_mm"])
        except (KeyError, TypeError, ValueError):
            return CommandResult.rejected(envelope.command_id, "distance_mm is required and must be a number")

        speed_mm_s = params.get("speed_mm_s")
        if speed_mm_s is not None:
            speed_mm_s = float(speed_mm_s)
        time_s = params.get("time_s")
        if time_s is not None:
            time_s = float(time_s)

        result = motion_service.jog(axis, distance_mm, speed_mm_s=speed_mm_s, time_s=time_s)
        return CommandResult(
            accepted=result.get("ok", False),
            command_id=envelope.command_id,
            state="COMPLETED" if result.get("ok") else "FAILED",
            reason=result.get("error"),
            result=result,
            completed_at=_now(),
        )

    return handle
