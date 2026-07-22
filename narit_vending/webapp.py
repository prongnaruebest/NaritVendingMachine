from __future__ import annotations

import argparse
import logging
import math
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from .motion import (
    ControlledStopError,
    EmergencyStopError,
    LimitTriggeredError,
    MotionError,
    build_controller,
    build_default_machine_config,
    load_hardware_config,
    load_machine_config,
    save_machine_config,
)
from .mqtt_service import MQTTService


_logger = logging.getLogger(__name__)


class APIInputError(ValueError):
    pass


class MotionService:
    def __init__(self, config_path: str | Path, hw_config_path: str | Path = "hardware_config.json") -> None:
        self.config_path = Path(config_path)
        self.hw_config_path = Path(hw_config_path)
        self.lock = threading.RLock()
        self.command_lock = threading.Lock()
        self.last_error = ""
        self.busy = False
        self.active_command = ""
        self.operation_phase = "ready"
        self.operation_message = "Controller ready"
        self.operation_axis: str | None = None
        self.homing = {axis: "not_homed" for axis in ("x", "y", "z")}
        self.command_id: str | None = None
        self.command_started_monotonic: float | None = None
        self.command_started_at: str | None = None
        self.command_estimated_duration_s: float | None = None
        self.armed_move: dict[str, object] | None = None
        self.completed_request_ids: dict[str, dict[str, object]] = {}

        if self.config_path.exists():
            config = load_machine_config(self.config_path)
        else:
            config = build_default_machine_config()
            save_machine_config(config, self.config_path)

        self.controller = build_controller(config, hw_config_path=str(self.hw_config_path))
        hw_config = load_hardware_config(str(self.hw_config_path))
        mqtt_config = hw_config.get("mqtt", {})
        self.mqtt_service = MQTTService(self, mqtt_config)
        self.mqtt_service.start()

    def status_payload(self) -> dict[str, object]:
        with self.lock:
            controller_status = self.controller.status()
            for axis_name, axis_status in ((name, controller_status[name]) for name in ("x", "y", "z")):
                if axis_status["is_homed"] and self.homing[axis_name] == "not_homed":
                    self.homing[axis_name] = "passed"

            slots = {
                code: {
                    "x_mm": slot.x_mm,
                    "y_mm": slot.y_mm,
                    "z_mm": slot.z_mm,
                    "product_name": slot.product_name,
                    "dispense_delay_ms": slot.dispense_delay_ms,
                }
                for code, slot in sorted(self.controller.config.slots.items(), key=_slot_sort_key)
            }
            return {
                "busy": self.busy,
                "active_command": self.active_command or None,
                "last_error": self.last_error,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "machine_state": controller_status["state"],
                "operation": {
                    "phase": self.operation_phase,
                    "message": self.operation_message,
                    "active_axis": self.operation_axis,
                    "homing": self.homing.copy(),
                },
                "motion_command": {
                    "command_id": self.command_id,
                    "command_type": self.active_command or None,
                    "started_at": self.command_started_at,
                    "elapsed_s": (
                        round(time.monotonic() - self.command_started_monotonic, 3)
                        if self.busy and self.command_started_monotonic is not None
                        else None
                    ),
                    "estimated_duration_s": self.command_estimated_duration_s,
                    "queue_depth": 0,
                    "trajectory_state": self.operation_phase,
                    "armed": self._armed_move_status(),
                },
                "safety": {
                    "estop_active": controller_status["estop"],
                    "stop_requested": self.controller.stop_requested(),
                    "controlled_stop_requested": self.controller.controlled_stop_requested(),
                },
                "status": controller_status,
                "slots": slots,
            }

    def _run(
        self,
        command_name: str,
        fn,
        *,
        motion_command: bool = True,
        command_id: str | None = None,
        estimated_duration_s: float | None = None,
    ):
        if motion_command and self.controller.stop_requested():
            return {"ok": False, "error": "Motion is stopped; reset alarms before issuing another command"}
        if not self.command_lock.acquire(blocking=False):
            return {"ok": False, "error": "Machine is busy with another command"}

        try:
            with self.lock:
                self.busy = True
                self.active_command = command_name
                self.command_id = command_id or uuid.uuid4().hex
                self.command_started_monotonic = time.monotonic()
                self.command_started_at = datetime.now(timezone.utc).isoformat()
                self.command_estimated_duration_s = estimated_duration_s
                self.last_error = ""
                self.operation_phase = "running"
                self.operation_message = f"Running {command_name.replace('_', ' ')}"
                if not command_name.startswith("home"):
                    self.operation_axis = None
                if motion_command:
                    self.controller.set_state("moving")

            result = fn()

            with self.lock:
                if motion_command:
                    self.controller.set_state("success")
                self.operation_phase = "completed"
                self.operation_message = f"Completed {command_name.replace('_', ' ')}"
            return {"ok": True, "result": result}
        except ControlledStopError as exc:
            with self.lock:
                self.controller.clear_controlled_stop()
                self.controller.set_state("idle")
                self.last_error = ""
                self.operation_phase = "stopped"
                self.operation_message = str(exc)
            _logger.info("Controlled stop: %s", exc)
            return {"ok": False, "controlled_stop": True, "error": str(exc)}
        except (MotionError, EmergencyStopError, LimitTriggeredError) as exc:
            with self.lock:
                self.last_error = str(exc)
                if motion_command:
                    self.controller.request_stop()
                    self.controller.set_state("alarm")
                self.operation_phase = "failed"
                self.operation_message = str(exc)
                if self.operation_axis:
                    self.homing[self.operation_axis] = "failed"
            _logger.warning("Motion error: %s", exc)
            return {"ok": False, "error": str(exc)}
        except Exception:
            with self.lock:
                self.last_error = "Internal controller error"
                if motion_command:
                    self.controller.request_stop()
                    self.controller.set_state("alarm")
                self.operation_phase = "failed"
                self.operation_message = "Internal controller error"
            _logger.exception("Unexpected error while running %s", command_name)
            return {"ok": False, "error": "Internal controller error"}
        finally:
            with self.lock:
                self.busy = False
                self.active_command = ""
                self.command_started_monotonic = None
                self.command_estimated_duration_s = None
            self.command_lock.release()

    def _armed_move_status(self) -> dict[str, object] | None:
        if self.armed_move is None:
            return None
        expires_at = float(self.armed_move["expires_at"])
        if time.monotonic() >= expires_at:
            self.armed_move = None
            return None
        return {
            "arm_token": self.armed_move["arm_token"],
            "expires_in_s": round(expires_at - time.monotonic(), 1),
            "plan": self.armed_move["plan"],
        }

    def _motion_safety_errors(self, *, require_homed: bool = True) -> list[str]:
        status = self.controller.status()
        errors: list[str] = []
        if self.busy:
            errors.append("Machine is busy with another command")
        if status["estop"]:
            errors.append("Emergency stop is active")
        if self.controller.stop_requested():
            errors.append("Software stop latch is active; reset alarms first")
        for axis_name in ("x", "y", "z"):
            axis = status[axis_name]
            if require_homed and not axis["is_homed"]:
                errors.append(f"{axis_name.upper()} axis is not homed")
            if axis["head_limit"] and axis["tail_limit"]:
                errors.append(f"{axis_name.upper()} axis has conflicting limit inputs")
        return errors

    def validate_motion_target(
        self,
        *,
        x_mm: float | None,
        y_mm: float | None,
        z_mm: float | None,
        speed_mm_s: float | None,
        time_s: float | None,
        timeout_s: float | None,
        acceleration_mm_s2: float | None,
        deceleration_mm_s2: float | None,
    ) -> dict[str, object]:
        with self.lock:
            errors = self._motion_safety_errors(require_homed=True)
            if errors:
                raise MotionError("; ".join(errors))
            plan = self.controller.plan_move(
                x_mm=x_mm,
                y_mm=y_mm,
                z_mm=z_mm,
                speed_mm_s=speed_mm_s,
                time_s=time_s,
            ).to_dict()
            duration_s = float(plan["duration_s"])
            if timeout_s is not None:
                if timeout_s <= 0:
                    raise MotionError("timeout_s must be greater than 0")
                if duration_s > timeout_s:
                    raise MotionError(
                        f"Estimated trajectory {duration_s:.2f} s exceeds timeout {timeout_s:.2f} s"
                    )

            requested_acceleration = acceleration_mm_s2
            requested_deceleration = deceleration_mm_s2
            axis_details: dict[str, object] = {}
            for axis_name, axis_plan in plan["axes"].items():
                config = self.controller.axes()[axis_name].config
                acceleration = config.acceleration if requested_acceleration is None else requested_acceleration
                deceleration = config.deceleration if requested_deceleration is None else requested_deceleration
                if not math.isfinite(acceleration) or acceleration <= 0 or acceleration > config.acceleration:
                    raise MotionError(
                        f"{axis_name.upper()}: acceleration must be within 0-{config.acceleration:.2f} mm/s^2"
                    )
                if not math.isfinite(deceleration) or deceleration <= 0 or deceleration > config.deceleration:
                    raise MotionError(
                        f"{axis_name.upper()}: deceleration must be within 0-{config.deceleration:.2f} mm/s^2"
                    )
                speed = float(axis_plan["speed_mm_s"])
                pulse_hz = float(axis_plan["pulse_hz"])
                if pulse_hz > 25000:
                    raise MotionError(
                        f"{axis_name.upper()}: pulse frequency {pulse_hz:.0f} Hz exceeds software limit 25000 Hz"
                    )
                axis_plan["acceleration_mm_s2"] = round(acceleration, 3)
                axis_plan["deceleration_mm_s2"] = round(deceleration, 3)
                axis_plan["acceleration_time_s"] = round(min(speed / acceleration, duration_s / 2), 3)
                axis_plan["deceleration_time_s"] = round(min(speed / deceleration, duration_s / 2), 3)
                axis_plan["following_error_mm"] = None
                axis_plan["drive_status"] = "NO DATA"
                axis_details[axis_name] = {
                    "valid": True,
                    "soft_limit": "PASS",
                    "homed": True,
                    "pulse_frequency_hz": pulse_hz,
                    "drive_feedback": "NO DATA",
                }
            plan["timeout_s"] = timeout_s
            plan["profile"] = "TRAPEZOIDAL"
            plan["master_axis"] = max(
                plan["axes"], key=lambda name: int(plan["axes"][name]["steps"]), default=None
            )
            return {
                "valid": True,
                "message": "Target passed backend safety validation",
                "plan": plan,
                "axes": axis_details,
                "warnings": ["Closed-loop drive feedback is not available from the current hardware API"],
            }

    def arm_motion_target(self, validation: dict[str, object], payload: dict[str, object]) -> dict[str, object]:
        arm_token = uuid.uuid4().hex
        with self.lock:
            self.armed_move = {
                "arm_token": arm_token,
                "expires_at": time.monotonic() + 20.0,
                "payload": payload,
                "plan": validation["plan"],
            }
        return {"ok": True, "arm_token": arm_token, "expires_in_s": 20, "plan": validation["plan"]}

    def execute_armed_motion(self, arm_token: str, request_id: str) -> dict[str, object]:
        if not request_id:
            return {"ok": False, "error": "request_id is required"}
        with self.lock:
            previous = self.completed_request_ids.get(request_id)
            if previous is not None:
                return previous | {"duplicate": True}
            armed = self.armed_move
            if armed is None or armed.get("arm_token") != arm_token:
                return {"ok": False, "error": "Move is not armed or arm token is invalid"}
            if time.monotonic() >= float(armed["expires_at"]):
                self.armed_move = None
                return {"ok": False, "error": "Armed move expired; validate and arm again"}
            payload = dict(armed["payload"])
            plan = dict(armed["plan"])
            self.armed_move = None
            self.completed_request_ids[request_id] = {"ok": False, "error": "Command is already executing"}

        result = self._run(
            "absolute_move",
            lambda: self.controller.move_to(
                x_mm=payload.get("x_mm"),
                y_mm=payload.get("y_mm"),
                z_mm=payload.get("z_mm"),
                speed_mm_s=payload.get("speed_mm_s"),
                time_s=payload.get("time_s"),
            ).to_dict(),
            command_id=request_id,
            estimated_duration_s=float(plan.get("duration_s", 0)),
        )
        with self.lock:
            self.completed_request_ids[request_id] = result
            if len(self.completed_request_ids) > 100:
                self.completed_request_ids.pop(next(iter(self.completed_request_ids)))
        return result

    def stop(self) -> dict[str, object]:
        self.controller.request_stop()
        with self.lock:
            self.controller.set_state("alarm")
            self.last_error = "Stop requested"
            self.operation_phase = "stopped"
            self.operation_message = "Stop requested by operator"
        return {"ok": True, "result": "stop requested"}

    def controlled_stop(self) -> dict[str, object]:
        if not self.busy:
            return {"ok": True, "result": "machine already idle"}
        self.controller.request_controlled_stop()
        with self.lock:
            self.operation_phase = "decelerating"
            self.operation_message = "Controlled stop requested; decelerating pulse train"
        return {"ok": True, "result": "controlled stop requested"}

    def clear_alarm(self) -> dict[str, object]:
        if self.controller.emergency_stop_active():
            return {"ok": False, "error": "Release the physical Emergency Stop before clearing alarms"}
        if not self.command_lock.acquire(blocking=False):
            return {"ok": False, "error": "Machine is busy; stop motion before clearing alarms"}
        try:
            with self.lock:
                self.controller.clear_stop()
                self.controller.set_state("idle")
                self.last_error = ""
                self.operation_phase = "ready"
                self.operation_message = "Alarm cleared; verify safety before continuing"
            return {"ok": True}
        finally:
            self.command_lock.release()

    def set_speed(self, speed_mm_s: float) -> dict[str, object]:
        with self.lock:
            requested_speed = float(speed_mm_s)
            if not math.isfinite(requested_speed) or requested_speed <= 0:
                return {"ok": False, "error": "speed_mm_s must be a finite number greater than 0"}
            self.controller.speed_override = min(requested_speed, 60.0)
            return {"ok": True, "speed_mm_s": self.controller.speed_override}

    def set_timer(self, seconds: float) -> dict[str, object]:
        with self.lock:
            requested_seconds = float(seconds)
            if not math.isfinite(requested_seconds) or requested_seconds < 0:
                return {"ok": False, "error": "duration_s must be a finite number greater than or equal to 0"}
            self.controller.timer_seconds = requested_seconds
            return {"ok": True, "timer_seconds": self.controller.timer_seconds}

    def _effective_motion(self, payload: dict[str, object]) -> tuple[float | None, float | None]:
        speed_mm_s = None
        time_s = None
        if payload.get("speed_mm_s") not in (None, ""):
            speed_mm_s = float(payload["speed_mm_s"])
            if not math.isfinite(speed_mm_s) or speed_mm_s <= 0:
                raise ValueError("speed_mm_s must be a finite number greater than 0")
        if payload.get("time_s") not in (None, ""):
            time_s = float(payload["time_s"])
            if not math.isfinite(time_s) or time_s <= 0:
                raise ValueError("time_s must be a finite number greater than 0")
        if speed_mm_s is None and self.controller.speed_override is not None:
            speed_mm_s = self.controller.speed_override
        if time_s is None and self.controller.timer_seconds > 0:
            time_s = self.controller.timer_seconds
        return speed_mm_s, time_s

    def start_motion(self, slot_code: str | None = None, speed_mm_s: float | None = None, time_s: float | None = None) -> dict[str, object]:
        if not slot_code:
            return {"ok": False, "error": "A slot is required to start a dispense operation"}
        return self._run("dispense", lambda: self.controller.move_to_slot(slot_code, speed_mm_s=speed_mm_s, time_s=time_s))

    def home_axis(self, axis_name: str) -> dict[str, object]:
        self._prepare_home((axis_name,))
        return self._run(f"home_{axis_name}", lambda: self.controller.home_axis(axis_name, progress=self._home_progress))

    def home_all(self) -> dict[str, object]:
        axes = self.controller.config.home_order
        self._prepare_home(axes)
        return self._run("home_all", lambda: self.controller.home_all(progress=self._home_progress))

    def _prepare_home(self, axes: tuple[str, ...] | list[str]) -> None:
        with self.lock:
            self.homing = {
                axis_name: "passed" if self.controller.axes()[axis_name].is_homed else "not_homed"
                for axis_name in ("x", "y", "z")
            }
            for axis_name in axes:
                self.homing[axis_name] = "waiting"
            self.operation_axis = None
            self.operation_phase = "queued"
            self.operation_message = "Waiting to start homing sequence"

    def _home_progress(self, axis_name: str, phase: str) -> None:
        with self.lock:
            self.operation_axis = axis_name
            self.homing[axis_name] = phase
            if phase == "searching":
                self.operation_message = f"Axis {axis_name.upper()} searching for home sensor"
            elif phase == "backoff":
                self.operation_message = f"Axis {axis_name.upper()} backing off home sensor"
            elif phase == "completed":
                self.operation_message = f"Axis {axis_name.upper()} home cycle completed"
            elif phase == "passed":
                self.operation_message = f"Axis {axis_name.upper()} homed successfully"

    def jog(self, axis_name: str, distance_mm: float, speed_mm_s: float | None = None, time_s: float | None = None) -> dict[str, object]:
        return self._run(
            f"jog_{axis_name}",
            lambda: self.controller.axes()[axis_name].move_mm(distance_mm, speed_mm_s=speed_mm_s, time_s=time_s),
        )

    def move_to_slot(self, slot_code: str, speed_mm_s: float | None = None, time_s: float | None = None) -> dict[str, object]:
        return self._run(f"goto_slot_{slot_code}", lambda: self.controller.move_to_slot(slot_code, speed_mm_s=speed_mm_s, time_s=time_s))

    def save_slot(
        self,
        slot_code: str,
        x_mm: float,
        y_mm: float,
        z_mm: float,
        product_name: str = "",
        dispense_delay_ms: int = 0,
    ) -> dict[str, object]:
        def action():
            self.controller.update_slot(
                slot_code,
                x_mm=x_mm,
                y_mm=y_mm,
                z_mm=z_mm,
                product_name=product_name,
                dispense_delay_ms=dispense_delay_ms,
            )
            save_machine_config(self.controller.config, self.config_path)

        return self._run(f"save_slot_{slot_code}", action, motion_command=False)

    def save_slot_from_current(self, slot_code: str) -> dict[str, object]:
        def action():
            current = self.controller.current_position()
            self.controller.update_slot(slot_code, **current)
            save_machine_config(self.controller.config, self.config_path)
            return current

        return self._run(f"save_current_slot_{slot_code}", action, motion_command=False)

    def move_to(
        self,
        x_mm: float | None = None,
        y_mm: float | None = None,
        z_mm: float | None = None,
        speed_mm_s: float | None = None,
        time_s: float | None = None,
    ) -> dict[str, object]:
        return self._run(
            "absolute_move",
            lambda: self.controller.move_to(x_mm=x_mm, y_mm=y_mm, z_mm=z_mm, speed_mm_s=speed_mm_s, time_s=time_s).to_dict(),
        )

    def plan_move(
        self,
        x_mm: float | None = None,
        y_mm: float | None = None,
        z_mm: float | None = None,
        speed_mm_s: float | None = None,
        time_s: float | None = None,
    ) -> dict[str, object]:
        with self.lock:
            return self.controller.plan_move(x_mm=x_mm, y_mm=y_mm, z_mm=z_mm, speed_mm_s=speed_mm_s, time_s=time_s).to_dict()

    def get_config(self) -> dict[str, object]:
        with self.lock:
            config = self.controller.config.to_dict()
            config["hardware"] = load_hardware_config(str(self.hw_config_path))
            return config

    def reset_slot(self, slot_code: str) -> dict[str, object]:
        def action():
            self.controller.update_slot(slot_code, x_mm=0.0, y_mm=0.0, z_mm=0.0)
            save_machine_config(self.controller.config, self.config_path)

        return self._run(f"reset_slot_{slot_code}", action, motion_command=False)

    def get_slot(self, slot_code: str) -> dict[str, object] | None:
        with self.lock:
            slot = self.controller.config.slots.get(str(slot_code))
            if slot is None:
                return None
            return {
                "x_mm": slot.x_mm,
                "y_mm": slot.y_mm,
                "z_mm": slot.z_mm,
                "product_name": slot.product_name,
                "dispense_delay_ms": slot.dispense_delay_ms,
            }

    def is_axis_homed(self, axis_name: str) -> dict[str, object]:
        with self.lock:
            axis = self.controller.axes().get(axis_name.lower())
            if axis is None:
                return {"ok": False, "error": f"Unknown axis '{axis_name}'"}
            return {"ok": True, "axis": axis_name.lower(), "is_homed": axis.is_homed}

    def is_all_homed(self) -> dict[str, object]:
        with self.lock:
            axes = self.controller.axes()
            result = {name: {"is_homed": ax.is_homed} for name, ax in axes.items()}
            all_homed = all(ax.is_homed for ax in axes.values())
            return {"ok": True, "axes": result, "all_homed": all_homed}


def _parse_optional_float(payload: dict[str, object], key: str) -> float | None:
    value = payload.get(key)
    if value in (None, ""):
        return None
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"{key} must be finite")
    return parsed


def _slot_sort_key(item: tuple[str, object]) -> tuple[int, int | str]:
    code = str(item[0])
    return (0, int(code)) if code.isdigit() else (1, code)


def _json_payload() -> dict[str, object]:
    if not request.get_data(cache=True):
        return {}
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise APIInputError("Request body must be a valid JSON object")
    return payload


def _motion_target_args(payload: dict[str, object]) -> dict[str, float | None]:
    speed_mm_s = _parse_optional_float(payload, "speed_mm_s")
    time_s = _parse_optional_float(payload, "time_s")
    timeout_s = _parse_optional_float(payload, "timeout_s")
    acceleration_mm_s2 = _parse_optional_float(payload, "acceleration_mm_s2")
    deceleration_mm_s2 = _parse_optional_float(payload, "deceleration_mm_s2")
    return {
        "x_mm": _parse_optional_float(payload, "x_mm"),
        "y_mm": _parse_optional_float(payload, "y_mm"),
        "z_mm": _parse_optional_float(payload, "z_mm"),
        "speed_mm_s": speed_mm_s,
        "time_s": time_s,
        "timeout_s": timeout_s,
        "acceleration_mm_s2": acceleration_mm_s2,
        "deceleration_mm_s2": deceleration_mm_s2,
    }


def create_app(config_path: str = "machine_config.json", hw_config_path: str = "hardware_config.json") -> Flask:
    app = Flask(__name__)
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    service = MotionService(config_path=config_path, hw_config_path=hw_config_path)
    app.extensions["motion_service"] = service

    @app.errorhandler(APIInputError)
    def handle_api_input_error(exc: APIInputError):
        return jsonify({"ok": False, "error": str(exc)}), 400

    @app.before_request
    def log_request():
        _logger.info("%s %s", request.method, request.path)

    @app.after_request
    def add_header(response):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/ping")
    def api_ping():
        return jsonify({"ok": True, "message": "pong"}), 200

    @app.get("/api/status")
    def api_status():
        return jsonify(service.status_payload())

    @app.get("/api/config")
    def api_config():
        return jsonify(service.get_config())

    @app.post("/api/plan/move")
    def api_plan_move():
        payload = _json_payload()
        try:
            speed_mm_s, time_s = service._effective_motion(payload)
            plan = service.plan_move(
                x_mm=_parse_optional_float(payload, "x_mm"),
                y_mm=_parse_optional_float(payload, "y_mm"),
                z_mm=_parse_optional_float(payload, "z_mm"),
                speed_mm_s=speed_mm_s,
                time_s=time_s,
            )
            return jsonify({"ok": True, "plan": plan} | service.status_payload()), 200
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "x_mm, y_mm, z_mm, speed_mm_s, and time_s must be numbers"}), 400
        except MotionError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.post("/api/motion/validate")
    @app.post("/api/motion/preview")
    def api_motion_validate():
        payload = _json_payload()
        try:
            args = _motion_target_args(payload)
            if args["x_mm"] is None and args["y_mm"] is None and args["z_mm"] is None:
                raise APIInputError("At least one target coordinate is required")
            validation = service.validate_motion_target(**args)
            return jsonify({"ok": True, "stage": "preview", **validation} | service.status_payload()), 200
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Motion parameters must be finite numbers"}), 400
        except MotionError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.post("/api/motion/arm")
    def api_motion_arm():
        payload = _json_payload()
        try:
            args = _motion_target_args(payload)
            if args["x_mm"] is None and args["y_mm"] is None and args["z_mm"] is None:
                raise APIInputError("At least one target coordinate is required")
            validation = service.validate_motion_target(**args)
            execution_payload = {
                key: args[key]
                for key in ("x_mm", "y_mm", "z_mm", "speed_mm_s", "time_s")
            }
            result = service.arm_motion_target(validation, execution_payload)
            return jsonify(result | validation | service.status_payload()), 200
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Motion parameters must be finite numbers"}), 400
        except MotionError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.post("/api/motion/execute")
    def api_motion_execute():
        payload = _json_payload()
        arm_token = str(payload.get("arm_token", ""))
        request_id = str(payload.get("request_id", ""))
        result = service.execute_armed_motion(arm_token, request_id)
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.post("/api/motion/controlled-stop")
    def api_motion_controlled_stop():
        result = service.controlled_stop()
        return jsonify(result | service.status_payload()), 200

    @app.post("/api/motion/abort")
    def api_motion_abort():
        result = service.stop()
        result["result"] = "motion abort requested"
        return jsonify(result | service.status_payload()), 200

    @app.post("/api/home/<axis_name>")
    def api_home_axis(axis_name: str):
        axis_name = axis_name.lower()
        if axis_name not in ("x", "y", "z", "all"):
            return jsonify({"ok": False, "error": f"Unknown axis '{axis_name}'. Use x, y, z, or all"}), 400
        result = service.home_all() if axis_name == "all" else service.home_axis(axis_name)
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.get("/api/home/<axis_name>/check")
    def api_home_check(axis_name: str):
        if axis_name.lower() == "all":
            return jsonify(service.is_all_homed())
        if axis_name.lower() not in ("x", "y", "z"):
            return jsonify({"ok": False, "error": f"Unknown axis '{axis_name}'"}), 400
        return jsonify(service.is_axis_homed(axis_name))

    @app.post("/api/jog")
    def api_jog():
        payload = _json_payload()
        axis = str(payload.get("axis", "")).lower()
        if axis not in ("x", "y", "z"):
            return jsonify({"ok": False, "error": "Field 'axis' must be one of: x, y, z"}), 400
        if "distance_mm" not in payload:
            return jsonify({"ok": False, "error": "Field 'distance_mm' is required"}), 400
        try:
            distance_mm = float(payload["distance_mm"])
            speed_mm_s, time_s = service._effective_motion(payload)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "distance_mm, speed_mm_s, and time_s must be numbers"}), 400
        result = service.jog(axis, distance_mm, speed_mm_s=speed_mm_s, time_s=time_s)
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.post("/api/move")
    def api_move():
        payload = _json_payload()
        try:
            x_mm = _parse_optional_float(payload, "x_mm")
            y_mm = _parse_optional_float(payload, "y_mm")
            z_mm = _parse_optional_float(payload, "z_mm")
            speed_mm_s, time_s = service._effective_motion(payload)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "x_mm, y_mm, z_mm, speed_mm_s, and time_s must be numbers"}), 400
        if x_mm is None and y_mm is None and z_mm is None:
            return jsonify({"ok": False, "error": "At least one of x_mm, y_mm, z_mm must be provided"}), 400
        result = service.move_to(x_mm=x_mm, y_mm=y_mm, z_mm=z_mm, speed_mm_s=speed_mm_s, time_s=time_s)
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.post("/api/start")
    def api_start():
        payload = _json_payload()
        slot_code = payload.get("slot") or payload.get("slot_code")
        try:
            speed_mm_s, time_s = service._effective_motion(payload)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "speed_mm_s and time_s must be numbers"}), 400
        result = service.start_motion(slot_code, speed_mm_s=speed_mm_s, time_s=time_s)
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.post("/api/slots/<slot_code>/goto")
    def api_goto_slot(slot_code: str):
        payload = _json_payload()
        try:
            speed_mm_s, time_s = service._effective_motion(payload)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "speed_mm_s and time_s must be numbers"}), 400
        result = service.move_to_slot(slot_code, speed_mm_s=speed_mm_s, time_s=time_s)
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.get("/api/slots")
    def api_slots():
        return jsonify(service.status_payload()["slots"])

    @app.get("/api/slots/<slot_code>")
    def api_get_slot(slot_code: str):
        slot = service.get_slot(slot_code)
        if slot is None:
            return jsonify({"error": f"Slot '{slot_code}' not found"}), 404
        return jsonify(slot)

    @app.post("/api/slots/<slot_code>")
    def api_save_slot(slot_code: str):
        payload = _json_payload()
        missing = [field for field in ("x_mm", "y_mm", "z_mm") if field not in payload]
        if missing:
            return jsonify({"ok": False, "error": f"Missing required fields: {', '.join(missing)}"}), 400
        try:
            result = service.save_slot(
                slot_code,
                x_mm=float(payload["x_mm"]),
                y_mm=float(payload["y_mm"]),
                z_mm=float(payload["z_mm"]),
                product_name=str(payload.get("product_name", "")),
                dispense_delay_ms=int(payload.get("dispense_delay_ms", 0)),
            )
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "x_mm, y_mm, z_mm, dispense_delay_ms must be numbers"}), 400
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.post("/api/slots/<slot_code>/save-current")
    def api_save_current(slot_code: str):
        result = service.save_slot_from_current(slot_code)
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.post("/api/slots/<slot_code>/reset")
    @app.delete("/api/slots/<slot_code>")
    def api_reset_slot(slot_code: str):
        result = service.reset_slot(slot_code)
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.post("/api/speed")
    def api_speed():
        payload = _json_payload()
        speed = payload.get("speed_mm_s", payload.get("speed"))
        if speed is None:
            return jsonify({"ok": False, "error": "Field 'speed_mm_s' or 'speed' is required"}), 400
        try:
            result = service.set_speed(float(speed))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "speed must be a number"}), 400
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.post("/api/timer")
    def api_timer():
        payload = _json_payload()
        duration = payload.get("duration_s", payload.get("timer_seconds", payload.get("duration")))
        if duration is None:
            return jsonify({"ok": False, "error": "Field 'duration_s' is required"}), 400
        try:
            result = service.set_timer(float(duration))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "duration_s must be a number"}), 400
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.post("/api/stop")
    def api_stop():
        return jsonify(service.stop() | service.status_payload()), 200

    @app.post("/api/clear-alarm")
    def api_clear_alarm():
        result = service.clear_alarm()
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    return app


def main() -> int:
    parser = argparse.ArgumentParser(description="Narit Vending web controller")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--config", default="machine_config.json")
    parser.add_argument("--hw-config", default="hardware_config.json")
    parser.add_argument("--log-file", default="narit_vending.log")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(args.log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    hw_config = load_hardware_config(args.hw_config)
    comm = hw_config.get("communication", {})
    host = comm.get("host", args.host)
    port = int(comm.get("port", args.port))

    _logger.info("Narit Vending starting - host=%s port=%s config=%s hw_config=%s", host, port, args.config, args.hw_config)

    app = create_app(config_path=args.config, hw_config_path=args.hw_config)
    app.run(host=host, port=port, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
