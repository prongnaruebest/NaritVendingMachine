"""MQTT proxy — adapts ControllerClient to the interface MQTTService expects.

MQTTService was built expecting a MotionService object with methods like
release_slot(), get_status() etc.  This thin proxy translates those calls
into IPC CommandEnvelope submissions so MQTT commands go through the same
safety gate as HTTP commands.

No GPIO is touched here.  This proxy lives in the web process.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from narit_vending.web.ipc_client import ControllerClient

_log = logging.getLogger(__name__)


class MqttControllerProxy:
    """Drop-in replacement for MotionService as seen by MQTTService.

    Only the methods that MQTTService calls are implemented here.
    """

    def __init__(self, ctrl: "ControllerClient") -> None:
        self._ctrl = ctrl

    def status_payload(self) -> dict[str, Any]:
        snap = self._ctrl.snapshot()
        from narit_vending.web.routes.status import _status_from_snapshot
        return _status_from_snapshot(snap)

    def _submit(self, command_type: str, params: dict[str, Any]) -> dict[str, Any]:
        from narit_vending.shared.commands import CommandEnvelope
        env = CommandEnvelope(command_type=command_type, source="mqtt", parameters=params)  # type: ignore[arg-type]
        result = self._ctrl.submit_command(env)
        return result.to_dict()

    # ── Methods called by MQTTService ─────────────────────────────────────────

    def release_slot(self, slot_code: str, request_id: str | None = None) -> dict[str, Any]:
        return self._submit("MOVE_TO_SLOT", {"slot_code": slot_code})

    def move_to_slot(self, slot_code: str, **kwargs: Any) -> dict[str, Any]:
        return self._submit("MOVE_TO_SLOT", {"slot_code": slot_code, **kwargs})

    def home_all(self) -> dict[str, Any]:
        return self._submit("HOME_ALL", {})

    def stop(self) -> dict[str, Any]:
        return self._submit("STOP", {})
