"""Web process entry point.

Usage:
    python -m narit_vending.web [--port 80] [--host 0.0.0.0]

Requires the controller process to be running first.
If the controller is unreachable, the web process starts anyway and
returns 503 for all command endpoints until the controller comes online.
"""

from __future__ import annotations

import argparse
import logging
import sys

_log = logging.getLogger("narit_vending.web")


def main() -> int:
    parser = argparse.ArgumentParser(description="NARIT Vending Web Monitor Process")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--hw-config", default="hardware_config.json")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    from narit_vending.web.ipc_client import ControllerClient

    ctrl = ControllerClient(timeout=2.0)
    if ctrl.ping():
        _log.info("Controller is reachable — web process starting")
    else:
        _log.warning("Controller not reachable at startup — will retry on requests")

    # Load hardware config for communication settings
    try:
        from narit_vending.motion import load_hardware_config
        hw_config = load_hardware_config(args.hw_config)
        comm = hw_config.get("communication", {})
        host = comm.get("host", args.host)
        port = int(comm.get("port", args.port))
    except Exception:
        host, port = args.host, args.port

    # Create Flask app
    from narit_vending.web.app import create_web_app
    app = create_web_app(ctrl_client=ctrl)

    # Attach MQTT service (monitor only — subscribes and publishes but does not touch GPIO)
    try:
        from narit_vending.mqtt_service import MQTTService
        mqtt_cfg = hw_config.get("mqtt", {}) if "hw_config" in dir() else {}  # type: ignore[used-before-def]
        # MQTT service needs a "motion_service" to dispatch commands
        # In web process mode we give it a proxy that uses ctrl.submit_command
        from narit_vending.web._mqtt_proxy import MqttControllerProxy
        mqtt_proxy = MqttControllerProxy(ctrl)
        mqtt_svc = MQTTService(mqtt_proxy, mqtt_cfg)
        mqtt_svc.start()
        app.extensions["mqtt_service"] = mqtt_svc
        _log.info("MQTT monitor service started")
    except Exception as exc:
        _log.warning("MQTT service not started: %s", exc)

    _log.info("Web process starting — host=%s port=%s", host, port)
    app.run(host=host, port=port, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
