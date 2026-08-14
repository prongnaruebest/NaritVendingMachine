"""Move command handlers (MOVE_TO, MOVE_TO_SLOT, DISPENSE, VALIDATE_TARGET, ARM_MOVE, EXECUTE_ARMED_MOVE)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from narit_vending.shared.commands import CommandEnvelope, CommandResult

_log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_float_or_none(params: dict, key: str) -> float | None:
    val = params.get(key)
    if val in (None, ""):
        return None
    return float(val)


def make_move_to_handler(motion_service: Any):
    from narit_vending.shared.commands import CommandResult

    def handle(envelope: "CommandEnvelope") -> "CommandResult":
        p = envelope.parameters
        result = motion_service.move_to(
            x_mm=_parse_float_or_none(p, "x_mm"),
            y_mm=_parse_float_or_none(p, "y_mm"),
            z_mm=_parse_float_or_none(p, "z_mm"),
            speed_mm_s=_parse_float_or_none(p, "speed_mm_s"),
            time_s=_parse_float_or_none(p, "time_s"),
        )
        return CommandResult(
            accepted=result.get("ok", False),
            command_id=envelope.command_id,
            state="COMPLETED" if result.get("ok") else "FAILED",
            reason=result.get("error"),
            result=result,
            completed_at=_now(),
        )

    return handle


def make_move_to_slot_handler(motion_service: Any):
    from narit_vending.shared.commands import CommandResult

    def handle(envelope: "CommandEnvelope") -> "CommandResult":
        p = envelope.parameters
        slot_code = str(p.get("slot_code", ""))
        if not slot_code:
            return CommandResult.rejected(envelope.command_id, "slot_code is required")
        result = motion_service.move_to_slot(
            slot_code,
            speed_mm_s=_parse_float_or_none(p, "speed_mm_s"),
            time_s=_parse_float_or_none(p, "time_s"),
        )
        return CommandResult(
            accepted=result.get("ok", False),
            command_id=envelope.command_id,
            state="COMPLETED" if result.get("ok") else "FAILED",
            reason=result.get("error"),
            result=result,
            completed_at=_now(),
        )

    return handle


def make_dispense_handler(motion_service: Any):
    from narit_vending.shared.commands import CommandResult

    def handle(envelope: "CommandEnvelope") -> "CommandResult":
        p = envelope.parameters
        slot_code = str(p.get("slot_code", ""))
        result = motion_service.start_motion(
            slot_code,
            speed_mm_s=_parse_float_or_none(p, "speed_mm_s"),
            time_s=_parse_float_or_none(p, "time_s"),
        )
        return CommandResult(
            accepted=result.get("ok", False),
            command_id=envelope.command_id,
            state="COMPLETED" if result.get("ok") else "FAILED",
            reason=result.get("error"),
            result=result,
            completed_at=_now(),
        )

    return handle


def make_validate_target_handler(motion_service: Any):
    from narit_vending.shared.commands import CommandResult

    def handle(envelope: "CommandEnvelope") -> "CommandResult":
        p = envelope.parameters
        try:
            speed_mm_s, time_s = motion_service._effective_motion(p)
            validation = motion_service.validate_motion_target(
                x_mm=_parse_float_or_none(p, "x_mm"),
                y_mm=_parse_float_or_none(p, "y_mm"),
                z_mm=_parse_float_or_none(p, "z_mm"),
                speed_mm_s=speed_mm_s,
                time_s=time_s,
                timeout_s=_parse_float_or_none(p, "timeout_s"),
                acceleration_mm_s2=_parse_float_or_none(p, "acceleration_mm_s2"),
                deceleration_mm_s2=_parse_float_or_none(p, "deceleration_mm_s2"),
            )
        except Exception as exc:
            return CommandResult.rejected(envelope.command_id, str(exc))
        return CommandResult(
            accepted=True,
            command_id=envelope.command_id,
            state="COMPLETED",
            result=validation,
            completed_at=_now(),
        )

    return handle


def make_arm_move_handler(motion_service: Any):
    from narit_vending.shared.commands import CommandResult

    def handle(envelope: "CommandEnvelope") -> "CommandResult":
        p = envelope.parameters
        validation = p.get("validation")
        payload = p.get("payload", p)
        if not validation:
            return CommandResult.rejected(envelope.command_id, "validation is required")
        result = motion_service.arm_motion_target(validation, payload)
        return CommandResult(
            accepted=result.get("ok", False),
            command_id=envelope.command_id,
            state="COMPLETED" if result.get("ok") else "FAILED",
            reason=result.get("error"),
            result=result,
            completed_at=_now(),
        )

    return handle


def make_execute_armed_move_handler(motion_service: Any):
    from narit_vending.shared.commands import CommandResult

    def handle(envelope: "CommandEnvelope") -> "CommandResult":
        p = envelope.parameters
        arm_token = str(p.get("arm_token", ""))
        request_id = str(p.get("request_id", envelope.idempotency_key))
        result = motion_service.execute_armed_motion(arm_token, request_id)
        return CommandResult(
            accepted=result.get("ok", False),
            command_id=envelope.command_id,
            state="COMPLETED" if result.get("ok") else "FAILED",
            reason=result.get("error"),
            result=result,
            completed_at=_now(),
        )

    return handle


def make_plan_move_handler(motion_service: Any):
    from narit_vending.shared.commands import CommandResult

    def handle(envelope: "CommandEnvelope") -> "CommandResult":
        p = envelope.parameters
        try:
            plan = motion_service.plan_move(
                x_mm=_parse_float_or_none(p, "x_mm"),
                y_mm=_parse_float_or_none(p, "y_mm"),
                z_mm=_parse_float_or_none(p, "z_mm"),
                speed_mm_s=_parse_float_or_none(p, "speed_mm_s"),
                time_s=_parse_float_or_none(p, "time_s"),
            )
        except Exception as exc:
            return CommandResult.rejected(envelope.command_id, str(exc))
        return CommandResult(
            accepted=True,
            command_id=envelope.command_id,
            state="COMPLETED",
            result=plan,
            completed_at=_now(),
        )

    return handle
