"""Command handlers for Controller-owned Demo Slot Sampling."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def make_demo_handler(service: Any, action: str):
    from narit_vending.shared.commands import CommandResult

    def handle(envelope):
        demo = service.demo_service
        if action == "configure":
            result = demo.configure(envelope.parameters)
        elif action == "start":
            result = demo.start(str(envelope.parameters.get("arm_token", "")))
        else:
            result = getattr(demo, action)()
        return CommandResult(
            accepted=bool(result.get("ok")), command_id=envelope.command_id,
            state="COMPLETED" if result.get("ok") else "FAILED",
            reason=result.get("error"), result=result,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

    return handle
