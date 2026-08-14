"""Motor test command handlers."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from narit_vending.shared.commands import CommandEnvelope, CommandResult

_log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_arm_motor_test_handler(motion_service: Any):
    from narit_vending.shared.commands import CommandResult

    def handle(envelope: "CommandEnvelope") -> "CommandResult":
        result = motion_service.set_motor_test_mode(armed=True)
        return CommandResult(
            accepted=result.get("ok", False),
            command_id=envelope.command_id,
            state="COMPLETED" if result.get("ok") else "FAILED",
            reason=result.get("error"),
            result=result,
            completed_at=_now(),
        )

    return handle


def make_disarm_motor_test_handler(motion_service: Any):
    from narit_vending.shared.commands import CommandResult

    def handle(envelope: "CommandEnvelope") -> "CommandResult":
        result = motion_service.set_motor_test_mode(armed=False)
        return CommandResult(
            accepted=result.get("ok", False),
            command_id=envelope.command_id,
            state="COMPLETED" if result.get("ok") else "FAILED",
            reason=result.get("error"),
            result=result,
            completed_at=_now(),
        )

    return handle


def make_run_motor_test_handler(motion_service: Any):
    from narit_vending.shared.commands import CommandResult

    def handle(envelope: "CommandEnvelope") -> "CommandResult":
        p = envelope.parameters
        axis = str(p.get("axis", "")).lower()
        if axis not in ("x", "y", "z"):
            return CommandResult.rejected(envelope.command_id, f"Invalid axis: {axis!r}")
        try:
            direction = str(p.get("direction", "forward"))
            pulse_count = int(p["pulse_count"])
            pulse_frequency_hz = float(p["pulse_frequency_hz"])
        except (KeyError, TypeError, ValueError) as exc:
            return CommandResult.rejected(envelope.command_id, f"Invalid parameters: {exc}")

        result = motion_service.run_motor_test(axis, direction, pulse_count, pulse_frequency_hz)
        return CommandResult(
            accepted=result.get("ok", False),
            command_id=envelope.command_id,
            state="COMPLETED" if result.get("ok") else "FAILED",
            reason=result.get("error"),
            result=result,
            completed_at=_now(),
        )

    return handle
