"""Slot management command handlers."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from narit_vending.shared.commands import CommandEnvelope, CommandResult

_log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_save_slot_handler(motion_service: Any):
    from narit_vending.shared.commands import CommandResult

    def handle(envelope: "CommandEnvelope") -> "CommandResult":
        params = envelope.parameters
        slot_code = str(params.get("slot_code", ""))
        if not slot_code:
            return CommandResult.rejected(envelope.command_id, "Missing slot_code")
        try:
            result = motion_service.save_slot(
                slot_code=slot_code,
                x_mm=float(params["x_mm"]),
                y_mm=float(params["y_mm"]),
                z_mm=float(params["z_mm"]),
                product_name=str(params.get("product_name", "")),
                dispense_delay_ms=int(params.get("dispense_delay_ms", 0)),
            )
            return CommandResult(
                accepted=result.get("ok", True) if isinstance(result, dict) else True,
                command_id=envelope.command_id,
                state="COMPLETED",
                result=result,
                completed_at=_now(),
            )
        except Exception as exc:
            _log.warning("Save slot failed: %s", exc)
            return CommandResult.rejected(envelope.command_id, f"Save slot error: {exc}")

    return handle


def make_save_slot_from_current_handler(motion_service: Any):
    from narit_vending.shared.commands import CommandResult

    def handle(envelope: "CommandEnvelope") -> "CommandResult":
        params = envelope.parameters
        slot_code = str(params.get("slot_code", ""))
        if not slot_code:
            return CommandResult.rejected(envelope.command_id, "Missing slot_code")
        try:
            result = motion_service.save_slot_from_current(slot_code=slot_code)
            return CommandResult(
                accepted=result.get("ok", True) if isinstance(result, dict) else True,
                command_id=envelope.command_id,
                state="COMPLETED",
                result=result,
                completed_at=_now(),
            )
        except Exception as exc:
            _log.warning("Save slot from current failed: %s", exc)
            return CommandResult.rejected(envelope.command_id, f"Save slot error: {exc}")

    return handle
