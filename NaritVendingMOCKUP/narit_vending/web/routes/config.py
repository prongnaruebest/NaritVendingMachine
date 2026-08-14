"""Config routes — proxy config get/save to controller via IPC."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from flask import Blueprint, jsonify, request

if TYPE_CHECKING:
    from narit_vending.web.ipc_client import ControllerClient

_log = logging.getLogger(__name__)


def _json_payload() -> dict[str, Any]:
    if not request.get_data(cache=True):
        return {}
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def make_config_bp(ctrl: "ControllerClient") -> Blueprint:
    bp = Blueprint("config", __name__)

    @bp.get("/api/config")
    def api_config():
        data = ctrl.get_effective_config()
        return jsonify(data), 200

    @bp.get("/api/config/effective")
    def api_effective_config():
        data = ctrl.get_effective_config()
        return jsonify(data), 200

    @bp.put("/api/config")
    def api_save_config():
        payload = _json_payload()
        result = ctrl.save_config(payload)
        ok = result.get("ok", False)
        # Handle error from controller
        if not ok and "error" in result:
            return jsonify(result), 400
        return jsonify({"ok": True, "config": result, "restart_required": True}), 200

    @bp.post("/api/config/apply")
    def api_apply_config():
        from narit_vending.shared.commands import CommandEnvelope
        env = CommandEnvelope(command_type="SCHEDULE_RESTART", source="http", parameters={})  # type: ignore[arg-type]
        result = ctrl.submit_command(env)
        return jsonify(result.to_dict()), 200 if result.accepted else 400

    return bp
