"""Controller-owned runtime setting command handlers."""

from __future__ import annotations

from typing import Any, Callable

from narit_vending.shared.commands import CommandEnvelope, CommandResult


def _result(envelope: CommandEnvelope, payload: dict[str, Any]) -> CommandResult:
    return CommandResult(
        accepted=bool(payload.get("ok")),
        command_id=envelope.command_id,
        state="COMPLETED" if payload.get("ok") else "REJECTED",
        reason=None if payload.get("ok") else str(payload.get("error") or "Setting rejected"),
        result=payload,
    )


def make_set_speed_handler(service: Any) -> Callable[[CommandEnvelope], CommandResult]:
    def handler(envelope: CommandEnvelope) -> CommandResult:
        try:
            speed = float(envelope.parameters["speed_mm_s"])
        except (KeyError, TypeError, ValueError):
            return CommandResult.rejected(envelope.command_id, "speed_mm_s must be a number")
        return _result(envelope, service.set_speed(speed))

    return handler


def make_set_timer_handler(service: Any) -> Callable[[CommandEnvelope], CommandResult]:
    def handler(envelope: CommandEnvelope) -> CommandResult:
        try:
            duration = float(envelope.parameters["duration_s"])
        except (KeyError, TypeError, ValueError):
            return CommandResult.rejected(envelope.command_id, "duration_s must be a number")
        return _result(envelope, service.set_timer(duration))

    return handler
