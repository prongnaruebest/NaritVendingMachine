"""Command routes — proxy all motion commands to the controller via IPC."""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any

from flask import Blueprint, jsonify, request

if TYPE_CHECKING:
    from narit_vending.web.ipc_client import ControllerClient

_log = logging.getLogger(__name__)


def _json_payload() -> dict[str, Any]:
    if not request.get_data(cache=True):
        return {}
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {}
    return payload


def _parse_opt_float(payload: dict, key: str) -> float | None:
    val = payload.get(key)
    if val in (None, ""):
        return None
    f = float(val)
    if not math.isfinite(f):
        raise ValueError(f"{key} must be finite")
    return f


def _submit(ctrl: "ControllerClient", command_type: str, params: dict, source: str = "http") -> dict:
    from narit_vending.shared.commands import CommandEnvelope
    env = CommandEnvelope(command_type=command_type, source=source, parameters=params)  # type: ignore[arg-type]
    result = ctrl.submit_command(env)
    return result.to_dict()


def make_commands_bp(ctrl: "ControllerClient") -> Blueprint:
    bp = Blueprint("commands", __name__)

    # ── Home ──────────────────────────────────────────────────────────────────

    @bp.post("/api/home/<axis_name>")
    def api_home_axis(axis_name: str):
        axis_name = axis_name.lower()
        if axis_name not in ("x", "y", "z", "all"):
            return jsonify({"ok": False, "error": f"Unknown axis '{axis_name}'"}), 400
        if axis_name == "all":
            r = _submit(ctrl, "HOME_ALL", {})
        else:
            r = _submit(ctrl, "HOME_AXIS", {"axis": axis_name})
        snap = ctrl.snapshot()
        return jsonify(r | _snap_status(snap)), 200 if r.get("accepted") else 400

    @bp.get("/api/home/<axis_name>/check")
    def api_home_check(axis_name: str):
        snap = ctrl.snapshot()
        if axis_name.lower() == "all":
            axes_result = {ax: {"is_homed": snap.axes[ax].is_homed} for ax in ("x", "y", "z") if ax in snap.axes}
            return jsonify({"ok": True, "axes": axes_result, "all_homed": all(v["is_homed"] for v in axes_result.values())})
        if axis_name.lower() not in ("x", "y", "z"):
            return jsonify({"ok": False, "error": f"Unknown axis '{axis_name}'"}), 400
        ax = snap.axes.get(axis_name.lower())
        return jsonify({"ok": True, "axis": axis_name.lower(), "is_homed": ax.is_homed if ax else False})

    # ── Jog ───────────────────────────────────────────────────────────────────

    @bp.post("/api/jog")
    def api_jog():
        payload = _json_payload()
        axis = str(payload.get("axis", "")).lower()
        if axis not in ("x", "y", "z"):
            return jsonify({"ok": False, "error": "Field 'axis' must be one of: x, y, z"}), 400
        if "distance_mm" not in payload:
            return jsonify({"ok": False, "error": "Field 'distance_mm' is required"}), 400
        try:
            distance_mm = float(payload["distance_mm"])
            speed_mm_s = _parse_opt_float(payload, "speed_mm_s")
            time_s = _parse_opt_float(payload, "time_s")
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "distance_mm, speed_mm_s, and time_s must be numbers"}), 400
        r = _submit(ctrl, "JOG", {"axis": axis, "distance_mm": distance_mm, "speed_mm_s": speed_mm_s, "time_s": time_s})
        snap = ctrl.snapshot()
        return jsonify(r | _snap_status(snap)), 200 if r.get("accepted") else 400

    # ── Move ──────────────────────────────────────────────────────────────────

    @bp.post("/api/move")
    def api_move():
        payload = _json_payload()
        try:
            x_mm = _parse_opt_float(payload, "x_mm")
            y_mm = _parse_opt_float(payload, "y_mm")
            z_mm = _parse_opt_float(payload, "z_mm")
            speed_mm_s = _parse_opt_float(payload, "speed_mm_s")
            time_s = _parse_opt_float(payload, "time_s")
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Coordinates and speed/time must be numbers"}), 400
        if x_mm is None and y_mm is None and z_mm is None:
            return jsonify({"ok": False, "error": "At least one of x_mm, y_mm, z_mm must be provided"}), 400
        r = _submit(ctrl, "MOVE_TO", {"x_mm": x_mm, "y_mm": y_mm, "z_mm": z_mm, "speed_mm_s": speed_mm_s, "time_s": time_s})
        snap = ctrl.snapshot()
        return jsonify(r | _snap_status(snap)), 200 if r.get("accepted") else 400

    # ── Plan / Validate / Arm / Execute ───────────────────────────────────────

    @bp.post("/api/plan/move")
    def api_plan_move():
        payload = _json_payload()
        try:
            r = _submit(ctrl, "PLAN_MOVE", payload)
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        snap = ctrl.snapshot()
        plan = (r.get("result") or {})
        return jsonify({"ok": r.get("accepted", False), "plan": plan} | _snap_status(snap)), 200

    @bp.post("/api/motion/validate")
    @bp.post("/api/motion/preview")
    def api_motion_validate():
        payload = _json_payload()
        try:
            r = _submit(ctrl, "VALIDATE_TARGET", payload)
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        snap = ctrl.snapshot()
        validation = r.get("result") or {}
        return jsonify({"ok": r.get("accepted", False), "stage": "preview", **validation} | _snap_status(snap)), 200

    @bp.post("/api/motion/arm")
    def api_motion_arm():
        payload = _json_payload()
        try:
            # First validate
            val_r = _submit(ctrl, "VALIDATE_TARGET", payload)
            validation = val_r.get("result") or {}
            # Then arm
            arm_r = _submit(ctrl, "ARM_MOVE", {"validation": validation, "payload": payload})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        snap = ctrl.snapshot()
        arm_data = arm_r.get("result") or {}
        return jsonify(arm_r | arm_data | validation | _snap_status(snap)), 200 if arm_r.get("accepted") else 400

    @bp.post("/api/motion/execute")
    def api_motion_execute():
        payload = _json_payload()
        arm_token = str(payload.get("arm_token", ""))
        request_id = str(payload.get("request_id", ""))
        r = _submit(ctrl, "EXECUTE_ARMED_MOVE", {"arm_token": arm_token, "request_id": request_id})
        snap = ctrl.snapshot()
        return jsonify(r | _snap_status(snap)), 200 if r.get("accepted") else 400

    # ── Start / Slots goto ────────────────────────────────────────────────────

    @bp.post("/api/start")
    def api_start():
        payload = _json_payload()
        slot_code = payload.get("slot") or payload.get("slot_code")
        try:
            speed_mm_s = _parse_opt_float(payload, "speed_mm_s")
            time_s = _parse_opt_float(payload, "time_s")
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "speed_mm_s and time_s must be numbers"}), 400
        r = _submit(ctrl, "DISPENSE", {"slot_code": slot_code, "speed_mm_s": speed_mm_s, "time_s": time_s})
        snap = ctrl.snapshot()
        return jsonify(r | _snap_status(snap)), 200 if r.get("accepted") else 400

    @bp.post("/api/slots/<slot_code>/goto")
    def api_goto_slot(slot_code: str):
        payload = _json_payload()
        try:
            speed_mm_s = _parse_opt_float(payload, "speed_mm_s")
            time_s = _parse_opt_float(payload, "time_s")
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "speed_mm_s and time_s must be numbers"}), 400
        r = _submit(ctrl, "MOVE_TO_SLOT", {"slot_code": slot_code, "speed_mm_s": speed_mm_s, "time_s": time_s})
        snap = ctrl.snapshot()
        return jsonify(r | _snap_status(snap)), 200 if r.get("accepted") else 400

    # ── Stop / Clear alarm ────────────────────────────────────────────────────

    @bp.post("/api/stop")
    def api_stop():
        r = _submit(ctrl, "STOP", {})
        snap = ctrl.snapshot()
        return jsonify(r | _snap_status(snap)), 200

    @bp.post("/api/motion/controlled-stop")
    def api_controlled_stop():
        r = _submit(ctrl, "CONTROLLED_STOP", {})
        snap = ctrl.snapshot()
        return jsonify(r | _snap_status(snap)), 200

    @bp.post("/api/motion/abort")
    def api_motion_abort():
        r = _submit(ctrl, "STOP", {})
        r["result"] = "motion abort requested"
        snap = ctrl.snapshot()
        return jsonify(r | _snap_status(snap)), 200

    @bp.post("/api/clear-alarm")
    def api_clear_alarm():
        r = _submit(ctrl, "CLEAR_ALARM", {})
        snap = ctrl.snapshot()
        return jsonify(r | _snap_status(snap)), 200 if r.get("accepted") else 400

    # ── Speed / Timer ─────────────────────────────────────────────────────────

    @bp.post("/api/speed")
    def api_speed():
        payload = _json_payload()
        speed = payload.get("speed_mm_s", payload.get("speed"))
        if speed is None:
            return jsonify({"ok": False, "error": "Field 'speed_mm_s' is required"}), 400
        try:
            r = _submit(ctrl, "SET_SPEED", {"speed_mm_s": float(speed)})
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "speed must be a number"}), 400
        snap = ctrl.snapshot()
        return jsonify(r | _snap_status(snap)), 200 if r.get("accepted") else 400

    @bp.post("/api/timer")
    def api_timer():
        payload = _json_payload()
        duration = payload.get("duration_s", payload.get("timer_seconds", payload.get("duration")))
        if duration is None:
            return jsonify({"ok": False, "error": "Field 'duration_s' is required"}), 400
        try:
            r = _submit(ctrl, "SET_SPEED", {"timer_seconds": float(duration)})
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "duration_s must be a number"}), 400
        snap = ctrl.snapshot()
        return jsonify(r | _snap_status(snap)), 200 if r.get("accepted") else 400

    # ── Motor test ────────────────────────────────────────────────────────────

    @bp.post("/api/maintenance/motor-test")
    def api_motor_test():
        payload = _json_payload()
        action = str(payload.get("action", "")).lower()
        if action not in ("arm", "cancel", "pulse"):
            return jsonify({"ok": False, "error": "Field 'action' must be arm, cancel, or pulse"}), 400
        if action == "arm":
            r = _submit(ctrl, "ARM_MOTOR_TEST", {})
        elif action == "cancel":
            r = _submit(ctrl, "DISARM_MOTOR_TEST", {})
        else:
            axis = str(payload.get("axis", "")).lower()
            direction = str(payload.get("direction", "forward")).lower()
            if axis not in ("x", "y", "z"):
                return jsonify({"ok": False, "error": "Field 'axis' must be one of: x, y, z"}), 400
            try:
                pulse_count = int(payload["pulse_count"])
                pulse_frequency_hz = float(payload["pulse_frequency_hz"])
            except (KeyError, TypeError, ValueError) as exc:
                return jsonify({"ok": False, "error": str(exc) or "Invalid motor test parameters"}), 400
            r = _submit(ctrl, "RUN_MOTOR_TEST", {
                "axis": axis,
                "direction": direction,
                "pulse_count": pulse_count,
                "pulse_frequency_hz": pulse_frequency_hz,
            })
        snap = ctrl.snapshot()
        return jsonify(r | _snap_status(snap)), 200 if r.get("accepted") else 400

    return bp


def _snap_status(snap) -> dict:
    """Build the minimal status dict merged into command responses."""
    from narit_vending.web.routes.status import _status_from_snapshot
    return _status_from_snapshot(snap)
