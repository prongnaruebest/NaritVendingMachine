"""Slot routes."""

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


def _submit(ctrl: "ControllerClient", command_type: str, params: dict) -> dict:
    from narit_vending.shared.commands import CommandEnvelope
    env = CommandEnvelope(command_type=command_type, source="http", parameters=params)  # type: ignore[arg-type]
    result = ctrl.submit_command(env)
    return result.to_dict()


def make_slots_bp(ctrl: "ControllerClient") -> Blueprint:
    bp = Blueprint("slots", __name__)

    @bp.get("/api/slots")
    def api_slots():
        # Slots are not in the snapshot — fetch from config
        config = ctrl.get_effective_config()
        slots = config.get("slots", {})
        return jsonify(slots)

    @bp.get("/api/slots/<slot_code>")
    def api_get_slot(slot_code: str):
        config = ctrl.get_effective_config()
        slot = config.get("slots", {}).get(str(slot_code))
        if slot is None:
            return jsonify({"error": f"Slot '{slot_code}' not found"}), 404
        return jsonify(slot)

    @bp.post("/api/slots/<slot_code>")
    def api_save_slot(slot_code: str):
        payload = _json_payload()
        missing = [f for f in ("x_mm", "y_mm", "z_mm") if f not in payload]
        if missing:
            return jsonify({"ok": False, "error": f"Missing required fields: {', '.join(missing)}"}), 400
        try:
            params = {
                "slot_code": slot_code,
                "x_mm": float(payload["x_mm"]),
                "y_mm": float(payload["y_mm"]),
                "z_mm": float(payload["z_mm"]),
                "product_name": str(payload.get("product_name", "")),
                "dispense_delay_ms": int(payload.get("dispense_delay_ms", 0)),
            }
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "x_mm, y_mm, z_mm, dispense_delay_ms must be numbers"}), 400
        r = _submit(ctrl, "SAVE_SLOT", params)
        snap = ctrl.snapshot()
        from narit_vending.web.routes.status import _status_from_snapshot
        return jsonify(r | _status_from_snapshot(snap)), 200 if r.get("accepted") else 400

    @bp.post("/api/slots/<slot_code>/save-current")
    def api_save_current(slot_code: str):
        r = _submit(ctrl, "SAVE_SLOT_FROM_CURRENT", {"slot_code": slot_code})
        snap = ctrl.snapshot()
        from narit_vending.web.routes.status import _status_from_snapshot
        return jsonify(r | _status_from_snapshot(snap)), 200 if r.get("accepted") else 400

    @bp.post("/api/slots/<slot_code>/reset")
    @bp.delete("/api/slots/<slot_code>")
    def api_reset_slot(slot_code: str):
        r = _submit(ctrl, "SAVE_SLOT", {"slot_code": slot_code, "x_mm": 0.0, "y_mm": 0.0, "z_mm": 0.0})
        snap = ctrl.snapshot()
        from narit_vending.web.routes.status import _status_from_snapshot
        return jsonify(r | _status_from_snapshot(snap)), 200 if r.get("accepted") else 400

    return bp
