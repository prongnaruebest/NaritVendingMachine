from __future__ import annotations

import argparse
import json
import threading
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


class MotionService:
    def __init__(self, config_path: str | Path, pulse_delay: float | None = None) -> None:
        self.config_path = Path(config_path)
        self.lock = threading.RLock()
        self.last_error = ""
        self.busy = False

        if self.config_path.exists():
            config = load_machine_config(self.config_path, pulse_delay=pulse_delay)
        else:
            config = build_default_machine_config(pulse_delay=pulse_delay or 0.0008)
            save_machine_config(config, self.config_path)

        self.controller = build_controller(config)

    def status_payload(self) -> dict[str, object]:
        with self.lock:
            slots = {
                code: {"x_mm": slot.x_mm, "y_mm": slot.y_mm, "z_mm": slot.z_mm}
                for code, slot in sorted(self.controller.config.slots.items(), key=lambda item: int(item[0]))
            }
            return {
                "busy": self.busy,
                "last_error": self.last_error,
                "status": self.controller.status(),
                "slots": slots,
            }

    def _run(self, fn):
        with self.lock:
            self.busy = True
            self.last_error = ""
            try:
                self.controller.clear_stop()
                result = fn()
                return {"ok": True, "result": result}
            except (MotionError, EmergencyStopError, LimitTriggeredError) as exc:
                self.last_error = str(exc)
                return {"ok": False, "error": str(exc)}
            finally:
                self.busy = False

    def stop(self) -> dict[str, object]:
        self.controller.request_stop()
        self.last_error = "Stop requested"
        return {"ok": True, "result": "stop requested"}

    def home_axis(self, axis_name: str) -> dict[str, object]:
        return self._run(lambda: self.controller.home_axis(axis_name))

    def home_all(self) -> dict[str, object]:
        return self._run(self.controller.home_all)

    def jog(self, axis_name: str, distance_mm: float) -> dict[str, object]:
        def action():
            axis = self.controller.axes()[axis_name]
            axis.move_mm(distance_mm)
        return self._run(action)

    def move_to_slot(self, slot_code: str) -> dict[str, object]:
        return self._run(lambda: self.controller.move_to_slot(slot_code))

    def save_slot(self, slot_code: str, x_mm: float, y_mm: float, z_mm: float) -> dict[str, object]:
        def action():
            self.controller.update_slot(slot_code, x_mm=x_mm, y_mm=y_mm, z_mm=z_mm)
            save_machine_config(self.controller.config, self.config_path)
        return self._run(action)

    def save_slot_from_current(self, slot_code: str) -> dict[str, object]:
        def action():
            current = self.controller.current_position()
            self.controller.update_slot(slot_code, **current)
            save_machine_config(self.controller.config, self.config_path)
            return current
        return self._run(action)


def create_app(config_path: str = "machine_config.json", pulse_delay: float | None = None) -> Flask:
    app = Flask(__name__)
    service = MotionService(config_path=config_path, pulse_delay=pulse_delay)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/status")
    def api_status():
        return jsonify(service.status_payload())

    @app.post("/api/home/<axis_name>")
    def api_home_axis(axis_name: str):
        if axis_name == "all":
            result = service.home_all()
        else:
            result = service.home_axis(axis_name.lower())
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.post("/api/jog")
    def api_jog():
        payload = request.get_json(force=True)
        result = service.jog(payload["axis"].lower(), float(payload["distance_mm"]))
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.post("/api/stop")
    def api_stop():
        result = service.stop()
        return jsonify(result | service.status_payload()), 200

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
        payload = request.get_json(force=True)
        result = service.save_slot(
            slot_code,
            x_mm=float(payload["x_mm"]),
            y_mm=float(payload["y_mm"]),
            z_mm=float(payload["z_mm"]),
        )
        status_code = 200 if result["ok"] else 400
        return jsonify(result | service.status_payload()), status_code

    @app.get("/api/slots")
    def api_slots():
        return jsonify(service.status_payload()["slots"])

    return app


def main() -> int:
    parser = argparse.ArgumentParser(description="Narit Vending web controller")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--config", default="machine_config.json")
    parser.add_argument("--pulse-delay", type=float, default=None)
    args = parser.parse_args()

    app = create_app(config_path=args.config, pulse_delay=args.pulse_delay)
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
