"""MQTT proxy — adapts ControllerClient to the interface MQTTService expects.

MQTTService was built expecting a MotionService object with methods like
release_slot(), get_status() etc.  This thin proxy translates those calls
into IPC CommandEnvelope submissions so MQTT commands go through the same
safety gate as HTTP commands.

No GPIO is touched here.  This proxy lives in the web process.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

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

    def _submit(
        self,
        command_type: str,
        params: dict[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        from narit_vending.shared.commands import CommandEnvelope
        envelope_args: dict[str, Any] = {
            "command_type": command_type,
            "source": "mqtt",
            "parameters": params,
        }
        if request_id:
            envelope_args["idempotency_key"] = request_id
        env = CommandEnvelope(**envelope_args)
        result = self._ctrl.submit_command(env)
        return result.to_dict()

    # ── Methods called by MQTTService ─────────────────────────────────────────

    def release_slot(self, slot_code: str, request_id: str | None = None) -> dict[str, Any]:
        return self._submit("MOVE_TO_SLOT", {"slot_code": slot_code}, request_id=request_id)

    def move_to_slot(
        self,
        slot_code: str,
        request_id: str | None = None,
        phase_callback: Callable[[str, dict[str, Any]], None] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        # MQTT uses exactly the same Controller-owned sequence as HMI.  Do not
        # split it into Web-side MOVE/HOME commands: that could change ordering
        # or allow another command to interleave between sequence stages.
        speed_mm_s = kwargs.get("speed_mm_s")
        params = {"slot_code": str(slot_code), "speed_mm_s": speed_mm_s}
        self._emit_phase(phase_callback, "moving", "SEQUENCE_STARTED")
        result = self._submit("RUN_SLOT_SEQUENCE", params, request_id=request_id)
        detail = result.get("result")
        if isinstance(detail, dict):
            return result | detail
        return result

    @staticmethod
    def _emit_phase(
        callback: Callable[[str, dict[str, Any]], None] | None,
        state: str,
        phase: str,
        **details: Any,
    ) -> None:
        if callback is not None:
            callback(state, {"phase": phase, **details})

    def _verify_slot_target(
        self,
        slot_code: str,
        *,
        axes: tuple[str, ...] = ("x", "y", "z"),
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        config = config or self._ctrl.get_effective_config()
        slot = dict(config.get("slots", {}).get(str(slot_code), {}))
        if not all(f"{axis}_mm" in slot for axis in axes):
            return {
                "target_reached": False,
                "reason": "TARGET_VERIFICATION_UNAVAILABLE",
            }

        snapshot = self._ctrl.snapshot()
        axis_config = dict(config.get("axes", {}))
        target = {axis: float(slot[f"{axis}_mm"]) for axis in axes}
        actual = {axis: float(snapshot.axes[axis].position_mm) for axis in axes}
        delta = {axis: actual[axis] - target[axis] for axis in axes}
        tolerance = {}
        for axis in axes:
            steps_per_mm = float(axis_config.get(axis, {}).get("steps_per_mm", 0.0) or 0.0)
            tolerance[axis] = max(0.05, 1.0 / steps_per_mm) if steps_per_mm > 0 else 0.05
        target_reached = all(abs(delta[axis]) <= tolerance[axis] for axis in axes)
        return {
            "target_reached": target_reached,
            "target_position_mm": {axis: round(value, 3) for axis, value in target.items()},
            "actual_position_mm": {axis: round(value, 3) for axis, value in actual.items()},
            "position_delta_mm": {axis: round(value, 3) for axis, value in delta.items()},
            "position_tolerance_mm": {axis: round(value, 3) for axis, value in tolerance.items()},
        }

    def _verify_home_position(self) -> dict[str, Any]:
        snapshot = self._ctrl.snapshot()
        actual = {axis: float(snapshot.axes[axis].position_mm) for axis in ("x", "y", "z")}
        homed = {axis: bool(snapshot.axes[axis].is_homed) for axis in ("x", "y", "z")}
        home_reached = all(homed.values()) and all(abs(position) <= 0.05 for position in actual.values())
        return {
            "home_reached": home_reached,
            "home_position_mm": {axis: round(value, 3) for axis, value in actual.items()},
            "axes_homed": homed,
        }

    def home_all(self) -> dict[str, Any]:
        return self._submit("HOME_ALL", {})

    def stop(self) -> dict[str, Any]:
        return self._submit("STOP", {})
