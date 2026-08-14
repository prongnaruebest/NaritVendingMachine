"""Stop/E-Stop/Clear-Alarm handlers — priority path, no motion lock required."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from narit_vending.shared.commands import CommandEnvelope, CommandResult

_log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_stop_handler(motion_service: Any):
    """Return a STOP handler bound to motion_service."""
    from narit_vending.shared.commands import CommandResult

    def handle(envelope: "CommandEnvelope") -> "CommandResult":
        result = motion_service.stop()
        return CommandResult(
            accepted=result.get("ok", False),
            command_id=envelope.command_id,
            state="COMPLETED" if result.get("ok") else "FAILED",
            reason=result.get("error"),
            result=result,
            completed_at=_now(),
        )

    return handle


def make_controlled_stop_handler(motion_service: Any):
    from narit_vending.shared.commands import CommandResult

    def handle(envelope: "CommandEnvelope") -> "CommandResult":
        result = motion_service.controlled_stop()
        return CommandResult(
            accepted=result.get("ok", False),
            command_id=envelope.command_id,
            state="COMPLETED" if result.get("ok") else "FAILED",
            reason=result.get("error"),
            result=result,
            completed_at=_now(),
        )

    return handle


def make_clear_alarm_handler(motion_service: Any):
    from narit_vending.shared.commands import CommandResult

    def handle(envelope: "CommandEnvelope") -> "CommandResult":
        result = motion_service.clear_alarm()
        return CommandResult(
            accepted=result.get("ok", False),
            command_id=envelope.command_id,
            state="COMPLETED" if result.get("ok") else "FAILED",
            reason=result.get("error"),
            result=result,
            completed_at=_now(),
        )

    return handle
