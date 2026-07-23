"""Health check routes."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from flask import Blueprint, jsonify

if TYPE_CHECKING:
    from narit_vending.web.ipc_client import ControllerClient

_log = logging.getLogger(__name__)


def make_health_bp(ctrl: "ControllerClient") -> Blueprint:
    bp = Blueprint("health", __name__)

    @bp.get("/health/live")
    def health_live():
        """Always returns 200 — the web process is running."""
        return jsonify({"status": "UP", "timestamp": datetime.now(timezone.utc).isoformat()}), 200

    @bp.get("/health/ready")
    def health_ready():
        """Returns 200 if the controller is reachable and config is valid."""
        alive = ctrl.ping()
        if not alive:
            return jsonify({
                "status": "DOWN",
                "service_ready": False,
                "machine_ready": False,
                "reason": "Controller IPC unreachable",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }), 503

        snap = ctrl.snapshot()
        axes_homed = all(snap.axes.get(ax, None) and snap.axes[ax].is_homed for ax in ("x", "y", "z"))
        machine_ready = (
            axes_homed
            and not snap.estop
            and snap.state not in ("ALARM", "MOVING", "CONFIG_REQUIRED", "E_STOP", "CONTROLLER_OFFLINE")
            and not snap.configuration_restart_required
        )
        service_ready = snap.state not in ("CONFIG_REQUIRED", "CONTROLLER_OFFLINE")
        return jsonify({
            "status": "UP" if service_ready else "DOWN",
            "service_ready": service_ready,
            "machine_ready": machine_ready,
            "machine_state": snap.state,
            "axes_homed": axes_homed,
            "config_revision": snap.config_revision,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 200 if service_ready else 503

    return bp
