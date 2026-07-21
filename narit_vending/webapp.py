from __future__ import annotations

import argparse
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from .motion import (
    EmergencyStopError,
    LimitTriggeredError,
    MotionError,
    build_controller,
    build_default_machine_config,
    load_machine_config,
    save_machine_config,
)


from .mqtt_service import MQTTService


_logger = logging.getLogger(__name__)


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
        self.operation_message = "Controller is ready for a command"
        self.operation_axis: str | None = None
        self.homing = {axis: "not_homed" for axis in ("x", "y", "z")}

        if self.config_path.exists():
            config = load_machine_config(self.config_path)
        else:
            config = build_default_machine_config()
            save_machine_config(config, self.config_path)

        self.controller = build_controller(config, hw_config_path=str(self.hw_config_path))

        # Initialize MQTT service if present in hardware config
        from .motion import load_hardware_config
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
                    "x_mm": slot.x_mm, "y_mm": slot.y_mm, "z_mm": slot.z_mm,
                    "product_name": slot.product_name,
                    "dispense_delay_ms": slot.dispense_delay_ms,
                }
                for code, slot in sorted(self.controller.config.slots.items(), key=lambda item: int(item[0]))
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
                "safety": {
                    "estop_active": controller_status["estop"],
                    "stop_requested": self.controller.stop_requested(),
                },
                "status": controller_status,
                "slots": slots,
            }

    def _run(self, command_name: str, fn):
        if not self.command_lock.acquire(blocking=False):
            return {"ok": False, "error": "Machine is busy with another command"}

        try:
            with self.lock:
                self.busy = True
                self.active_command = command_name
                self.last_error = ""
                self.operation_phase = "running"
                self.operation_message = f"Running {command_name.replace('_', ' ')}"
                if not command_name.startswith("home"):
                    self.operation_axis = None
                self.controller.clear_stop()
                self.controller.set_state("moving")

            result = fn()

            with self.lock:
                self.controller.set_state("success")
                self.operation_phase = "completed"
                self.operation_message = f"Completed {command_name.replace('_', ' ')}"
            return {"ok": True, "result": result}
        except (MotionError, EmergencyStopError, LimitTriggeredError) as exc:
            with self.lock:
                self.last_error = str(exc)
                self.controller.set_state("alarm")
                self.operation_phase = "failed"
                self.operation_message = str(exc)
                if self.operation_axis:
                    self.homing[self.operation_axis] = "failed"
            _logger.warning("Motion error: %s", exc)
            return {"ok": False, "error": str(exc)}
        finally:
            with self.lock:
                self.busy = False
                self.active_command = ""
            self.command_lock.release()

    def stop(self) -> dict[str, object]:
        # Stop is deliberately not queued behind an active motion command.
        self.controller.request_stop()
        with self.lock:
            self.controller.set_state("alarm")
            self.last_error = "Stop requested"
            self.operation_phase = "stopped"
            self.operation_message = "Stop requested by operator"
        return {"ok": True, "result": "stop requested"}

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
                self.operation_message = "Alarm cleared; verify machine is safe before continuing"
            return {"ok": True}
        finally:
            self.command_lock.release()

    def set_speed(self, speed_mm_s: float) -> dict[str, object]:
        with self.lock:
            speed = max(0.1, min(float(speed_mm_s), 100.0))
            self.controller.speed_override = speed
            return {"ok": True, "speed_mm_s": speed}

    def set_timer(self, seconds: float) -> dict[str, object]:
        with self.lock:
            timer = max(0.0, float(seconds))
            self.controller.timer_seconds = timer
            return {"ok": True, "timer_seconds": timer}

    def start_motion(self, slot_code: str | None = None) -> dict[str, object]:
        if not slot_code:
            return {"ok": False, "error": "A slot is required to start a dispense operation"}
        return self._run("dispense", lambda: self.controller.move_to_slot(slot_code))

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
            if phase == "homing":
                self.operation_message = f"Homing axis {axis_name.upper()}"
            elif phase == "passed":
                self.operation_message = f"Axis {axis_name.upper()} homed successfully"

    def jog(self, axis_name: str, distance_mm: float, speed_mm_s: float | None = None) -> dict[str, object]:
        def action():
            axis = self.controller.axes()[axis_name]
            axis.move_mm(distance_mm, speed_mm_s=speed_mm_s)
        return self._run(f"jog_{axis_name}", action)

    def move_to_slot(self, slot_code: str) -> dict[str, object]:
        return self._run(f"goto_slot_{slot_code}", lambda: self.controller.move_to_slot(slot_code))

    def save_slot(self, slot_code: str, x_mm: float, y_mm: float, z_mm: float,
                   product_name: str = "", dispense_delay_ms: int = 0) -> dict[str, object]:
        def action():
            self.controller.update_slot(slot_code, x_mm=x_mm, y_mm=y_mm, z_mm=z_mm,
                                         product_name=product_name, dispense_delay_ms=dispense_delay_ms)
            save_machine_config(self.controller.config, self.config_path)
        return self._run(f"save_slot_{slot_code}", action)

    def save_slot_from_current(self, slot_code: str) -> dict[str, object]:
        def action():
            current = self.controller.current_position()
            self.controller.update_slot(slot_code, **current)
            save_machine_config(self.controller.config, self.config_path)
            return current
        return self._run(f"save_current_slot_{slot_code}", action)

    def move_to(self, x_mm: float | None = None, y_mm: float | None = None, z_mm: float | None = None, speed_mm_s: float | None = None) -> dict[str, object]:
        def action():
            self.controller.move_to(x_mm=x_mm, y_mm=y_mm, z_mm=z_mm, speed_mm_s=speed_mm_s)
        return self._run("absolute_move", action)

    def get_config(self) -> dict[str, object]:
        with self.lock:
            return self.controller.config.to_dict()

    def reset_slot(self, slot_code: str) -> dict[str, object]:
        def action():
            self.controller.update_slot(slot_code, x_mm=0.0, y_mm=0.0, z_mm=0.0)
            save_machine_config(self.controller.config, self.config_path)
        return self._run(f"reset_slot_{slot_code}", action)

    def get_slot(self, slot_code: str) -> dict[str, object] | None:
        with self.lock:
            slot = self.controller.config.slots.get(str(slot_code))
            if slot is None:
                return None
            return {
                "x_mm": slot.x_mm, "y_mm": slot.y_mm, "z_mm": slot.z_mm,
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
        """ดึงสถานะ Home ของทุกแกนในครั้งเดียว"""
        with self.lock:
            axes = self.controller.axes()
            result = {
                name: {"is_homed": ax.is_homed}
                for name, ax in axes.items()
            }
            all_homed = all(ax.is_homed for ax in axes.values())
            return {"ok": True, "axes": result, "all_homed": all_homed}


def create_app(config_path: str = "machine_config.json", hw_config_path: str = "hardware_config.json") -> Flask:
    app = Flask(__name__)
    service = MotionService(config_path=config_path, hw_config_path=hw_config_path)

    @app.before_request
    def log_request():
        _logger.info("%s %s", request.method, request.path)

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/status")
    def api_status():
        return jsonify(service.status_payload())

    @app.post("/api/home/<axis_name>")
    def api_home_axis(axis_name: str):
        axis_name = axis_name.lower()
        if axis_name not in ("x", "y", "z", "all"):
            return jsonify({"ok": False, "error": f"Unknown axis '{axis_name}'. Use x, y, z, or all"}), 400
        if axis_name == "all":
            result = service.home_all()
        else:
            result = service.home_axis(axis_name)
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.post("/api/jog")
    def api_jog():
        payload = request.get_json(force=True) or {}
        axis = payload.get("axis", "")
        if not axis or axis.lower() not in ("x", "y", "z"):
            return jsonify({"ok": False, "error": "Field 'axis' must be one of: x, y, z"}), 400
        if "distance_mm" not in payload:
            return jsonify({"ok": False, "error": "Field 'distance_mm' is required"}), 400
        try:
            distance_mm = float(payload["distance_mm"])
            
            speed_mm_s = None
            if "time_s" in payload and payload["time_s"]:
                time_s = float(payload["time_s"])
                if time_s > 0:
                    speed_mm_s = abs(distance_mm) / time_s
            elif "speed_mm_s" in payload and payload["speed_mm_s"]:
                speed_mm_s = float(payload["speed_mm_s"])
                
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "distance_mm, speed_mm_s, or time_s must be a number"}), 400
        result = service.jog(axis.lower(), distance_mm, speed_mm_s=speed_mm_s)
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.post("/api/stop")
    def api_stop():
        result = service.stop()
        return jsonify(result | service.status_payload()), 200

    @app.post("/api/clear-alarm")
    def api_clear_alarm():
        result = service.clear_alarm()
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.post("/api/speed")
    def api_speed():
        payload = request.get_json(force=True, silent=True) or {}
        speed = payload.get("speed_mm_s", payload.get("speed"))
        if speed is None:
            return jsonify({"ok": False, "error": "Field 'speed_mm_s' or 'speed' is required"}), 400
        try:
            val = float(speed)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "speed must be a number"}), 400
        result = service.set_speed(val)
        return jsonify(result | service.status_payload()), 200

    @app.post("/api/timer")
    def api_timer():
        payload = request.get_json(force=True, silent=True) or {}
        duration = payload.get("duration_s", payload.get("timer_seconds", payload.get("duration")))
        if duration is None:
            return jsonify({"ok": False, "error": "Field 'duration_s' is required"}), 400
        try:
            val = float(duration)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "duration_s must be a number"}), 400
        result = service.set_timer(val)
        return jsonify(result | service.status_payload()), 200

    @app.post("/api/start")
    def api_start():
        payload = request.get_json(force=True, silent=True) or {}
        slot_code = payload.get("slot") or payload.get("slot_code")
        result = service.start_motion(slot_code)
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.post("/api/slots/<slot_code>/goto")
    def api_goto_slot(slot_code: str):
        result = service.move_to_slot(slot_code)
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.post("/api/slots/<slot_code>/save-current")
    def api_save_current(slot_code: str):
        result = service.save_slot_from_current(slot_code)
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.post("/api/slots/<slot_code>")
    def api_save_slot(slot_code: str):
        payload = request.get_json(force=True) or {}
        missing = [f for f in ("x_mm", "y_mm", "z_mm") if f not in payload]
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
            return jsonify({"ok": False, "error": "x_mm, y_mm, z_mm must be numbers"}), 400
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.get("/api/slots")
    def api_slots():
        return jsonify(service.status_payload()["slots"])

    # --- New endpoints ---

    @app.get("/api/ping")
    def api_ping():
        """ตรวจสอบการเชื่อมต่อ — เร็ว ไม่ query ข้อมูลอื่น"""
        return jsonify({"ok": True, "message": "pong"}), 200

    @app.get("/api/config")
    def api_config():
        """ดึงค่า Config ของแต่ละแกน (steps_per_mm, max_travel_mm, pulse_pin ฯลฯ)"""
        return jsonify(service.get_config())

    @app.post("/api/move")
    def api_move():
        """สั่งเคลื่อนที่ตรง ๆ ด้วย X/Y/Z พร้อมกันทีเดียว (รองรับ speed/time)"""
        payload = request.get_json(force=True) or {}
        try:
            x_mm = float(payload["x_mm"]) if "x_mm" in payload else None
            y_mm = float(payload["y_mm"]) if "y_mm" in payload else None
            z_mm = float(payload["z_mm"]) if "z_mm" in payload else None
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "x_mm, y_mm, and z_mm must be numbers"}), 400
        if x_mm is None and y_mm is None and z_mm is None:
            return jsonify({"ok": False, "error": "At least one of x_mm, y_mm, z_mm must be provided"}), 400
            
        speed_mm_s = None
        try:
            if "time_s" in payload and payload["time_s"]:
                time_s = float(payload["time_s"])
                if time_s > 0:
                    # Calculate max distance to find required speed
                    current_pos = service.controller.current_position()
                    dist_x = abs(x_mm - current_pos["x_mm"]) if x_mm is not None else 0
                    dist_y = abs(y_mm - current_pos["y_mm"]) if y_mm is not None else 0
                    dist_z = abs(z_mm - current_pos["z_mm"]) if z_mm is not None else 0
                    max_dist = max(dist_x, dist_y, dist_z)
                    speed_mm_s = max_dist / time_s
            elif "speed_mm_s" in payload and payload["speed_mm_s"]:
                speed_mm_s = float(payload["speed_mm_s"])
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "speed_mm_s or time_s must be a number"}), 400
            
        result = service.move_to(x_mm=x_mm, y_mm=y_mm, z_mm=z_mm, speed_mm_s=speed_mm_s)
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.get("/api/slots/<slot_code>")
    def api_get_slot(slot_code: str):
        """ดึงพิกัดของช่องเดียว"""
        slot = service.get_slot(slot_code)
        if slot is None:
            return jsonify({"error": f"Slot '{slot_code}' not found"}), 404
        return jsonify(slot)

    @app.post("/api/slots/<slot_code>/reset")
    def api_reset_slot(slot_code: str):
        """Reset พิกัด Slot กลับเป็น 0,0,0"""
        result = service.reset_slot(slot_code)
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.delete("/api/slots/<slot_code>")
    def api_delete_slot(slot_code: str):
        """ลบพิกัดช่องออก (reset กลับเป็น 0,0,0)"""
        result = service.reset_slot(slot_code)
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.get("/api/home/<axis_name>/check")
    def api_home_check(axis_name: str):
        """ตรวจสอบว่าแกนนั้น Home แล้วหรือยัง (ไม่สั่ง Home)"""
        if axis_name.lower() == "all":
            return jsonify(service.is_all_homed())
        if axis_name.lower() not in ("x", "y", "z"):
            return jsonify({"ok": False, "error": f"Unknown axis '{axis_name}'"}), 400
        result = service.is_axis_homed(axis_name)
        return jsonify(result)

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

    from .motion import load_hardware_config
    hw_config = load_hardware_config(args.hw_config)
    comm = hw_config.get("communication", {})
    host = comm.get("host", args.host)
    port = int(comm.get("port", args.port))

    _logger.info("Narit Vending starting — host=%s port=%s config=%s hw_config=%s", host, port, args.config, args.hw_config)

    app = create_app(config_path=args.config, hw_config_path=args.hw_config)
    app.run(host=host, port=port, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
