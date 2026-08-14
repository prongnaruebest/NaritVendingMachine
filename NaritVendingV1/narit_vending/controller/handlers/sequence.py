"""CommandBus handler for the Controller-owned slot sequence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from narit_vending.shared.commands import CommandEnvelope, CommandResult


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_slot_sequence_handler(sequence_service: Any):
    from narit_vending.shared.commands import CommandResult

    def handle(envelope: "CommandEnvelope") -> "CommandResult":
        params = envelope.parameters
        slot_code = str(params.get("slot_code", ""))
        if not slot_code:
            return CommandResult.rejected(envelope.command_id, "slot_code is required")
        value = params.get("speed_mm_s")
        try:
            speed_mm_s = None if value in (None, "") else float(value)
        except (TypeError, ValueError):
            return CommandResult.rejected(envelope.command_id, "speed_mm_s must be a number")
        callback = params.get("_phase_callback")
        result = sequence_service.run(
            slot_code,
            speed_mm_s=speed_mm_s,
            request_id=envelope.idempotency_key,
            phase_callback=callback if callable(callback) else None,
        )
        return CommandResult(
            accepted=bool(result.get("ok", False)),
            command_id=envelope.command_id,
            state="COMPLETED" if result.get("ok") else "FAILED",
            reason=result.get("error"),
            result=result,
            completed_at=_now(),
        )

    return handle
