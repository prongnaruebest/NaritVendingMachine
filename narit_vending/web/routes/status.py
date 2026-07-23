"""Status and MQTT monitor routes."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from flask import Blueprint, jsonify

if TYPE_CHECKING:
    from narit_vending.web.ipc_client import ControllerClient

_log = logging.getLogger(__name__)

_MOTOR_TEST_MAX_DURATION_S = 10.0
_MOTOR_TEST_MAX_FREQUENCY_HZ = 1000.0
_MOTOR_TEST_MAX_PULSES = 10000


def _status_from_snapshot(snap) -> dict:
    """Convert MachineSnapshot to the legacy /api/status JSON shape.

    Keeps the exact same JSON structure the HMI frontend expects so no
    frontend changes are required during the migration period.
    """
    axes_data = {}
    for ax in ("x", "y", "z"):
        axis_snap = snap.axes.get(ax)
        if axis_snap:
            axes_data[ax] = axis_snap.to_dict()
        else:
            axes_data[ax] = {
                "name": ax,
                "position_mm": 0.0,
                "position_steps": 0,
                "is_homed": False,
                "head_limit": False,
                "tail_limit": False,
            }

    elapsed = None
    if snap.busy and snap.command_started_at:
        try:
            started = datetime.fromisoformat(snap.command_started_at.replace("Z", "+00:00"))
            elapsed = round((datetime.now(timezone.utc) - started).total_seconds(), 3)
        except Exception:
            pass

    return {
        "busy": snap.busy,
        "active_command": snap.active_command or None,
        "last_error": snap.last_error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "machine_state": snap.state,
        "operation": {
            "phase": snap.operation_phase,
            "message": snap.operation_message,
            "active_axis": snap.operation_axis,
            "homing": snap.homing,
        },
        "motion_command": {
            "command_id": snap.command_id,
            "command_type": snap.active_command or None,
            "started_at": snap.command_started_at,
            "elapsed_s": elapsed,
            "estimated_duration_s": snap.command_estimated_duration_s,
            "queue_depth": 0,
            "trajectory_state": snap.operation_phase,
            "armed": None,  # Populated by controller if arm token exists
        },
        "safety": {
            "estop_active": snap.estop,
            "stop_requested": snap.stop_requested,
            "controlled_stop_requested": snap.controlled_stop_requested,
            "configuration_restart_required": snap.configuration_restart_required,
            "motor_test": {
                "armed": snap.motor_test_armed,
                "expires_in_s": None,
                "max_duration_s": _MOTOR_TEST_MAX_DURATION_S,
                "max_frequency_hz": _MOTOR_TEST_MAX_FREQUENCY_HZ,
                "max_pulses": _MOTOR_TEST_MAX_PULSES,
                "scope": "motor_test_page_only",
            },
        },
        "status": {
            "state": snap.state.lower() if snap.state else "unknown",
            "estop": snap.estop,
            **axes_data,
        },
        # slots will be populated by the controller snapshot or separately
        "slots": {},
    }


def make_status_bp(ctrl: "ControllerClient") -> Blueprint:
    bp = Blueprint("status", __name__)

    @bp.get("/api/status")
    def api_status():
        snap = ctrl.snapshot()
        return jsonify(_status_from_snapshot(snap))

    @bp.get("/api/mqtt/status")
    def api_mqtt_status():
        # MQTT service is still running in the web process (it was already there)
        # Get it from Flask app extensions if available
        from flask import current_app
        mqtt_svc = current_app.extensions.get("mqtt_service")
        if mqtt_svc is not None:
            return jsonify(mqtt_svc.status_payload()), 200
        return jsonify({"enabled": False, "connected": False, "state": "MQTT_NOT_CONFIGURED"}), 200

    return bp
