from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .webapp import MotionService

_logger = logging.getLogger(__name__)

try:
    import paho.mqtt.client as mqtt
    HAS_PAHO = True
except ImportError:
    mqtt = None
    HAS_PAHO = False


class MQTTService:
    def __init__(self, motion_service: MotionService, mqtt_config: dict[str, Any]) -> None:
        self.service = motion_service
        self.config = mqtt_config
        self.enabled = bool(mqtt_config.get("enabled", False))
        self.prefix = mqtt_config.get("topic_prefix", "vending/machine_01")
        self.client: Any = None

        if not self.enabled:
            _logger.info("MQTT service is disabled in hardware_config.json")
            return

        if not HAS_PAHO:
            _logger.warning("paho-mqtt library not installed. MQTT service will not run.")
            return

        client_id = mqtt_config.get("client_id", "vending_machine_01")
        self.client = mqtt.Client(client_id=client_id)

        if mqtt_config.get("username"):
            self.client.username_pw_set(
                mqtt_config["username"],
                mqtt_config.get("password", "")
            )

        # Configure Last Will and Testament (LWT)
        lwt_topic = f"{self.prefix}/heartbeat"
        lwt_payload = json.dumps({"online": False, "reason": "connection_lost"})
        self.client.will_set(lwt_topic, payload=lwt_payload, qos=1, retain=True)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def start(self) -> None:
        if not self.enabled or not self.client:
            return
        broker = self.config.get("broker", "broker.emqx.io")
        port = int(self.config.get("port", 1883))
        keepalive = int(self.config.get("keepalive_s", 60))

        try:
            _logger.info("Connecting to MQTT broker %s:%d (prefix=%s)", broker, port, self.prefix)
            self.client.connect_async(broker, port, keepalive=keepalive)
            self.client.loop_start()
        except Exception as exc:
            _logger.error("Failed to connect to MQTT broker: %s", exc)

    def _on_connect(self, client: Any, userdata: Any, flags: Any, rc: int) -> None:
        _logger.info("Connected to MQTT broker with result code %d", rc)
        if rc == 0:
            # Subscribe to command topics
            self.client.subscribe(f"{self.prefix}/cmd/+")
            # Publish online heartbeat
            self.client.publish(
                f"{self.prefix}/heartbeat",
                json.dumps({"online": True}),
                qos=1,
                retain=True
            )

    def _on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        topic = str(msg.topic)
        try:
            payload = json.loads(msg.payload.decode("utf-8")) if msg.payload else {}
        except Exception:
            payload = {}

        _logger.info("MQTT Received [%s]: %s", topic, payload)

        if topic.endswith("/cmd/dispense") or topic.endswith("/cmd/start"):
            slot = payload.get("slot") or payload.get("slot_code")
            res = self.service.start_motion(slot)
            self.publish_response("dispense", res)

        elif topic.endswith("/cmd/stop"):
            res = self.service.stop()
            self.publish_response("stop", res)

        elif topic.endswith("/cmd/home"):
            axis = payload.get("axis", "all").lower()
            if axis == "all":
                res = self.service.home_all()
            else:
                res = self.service.home_axis(axis)
            self.publish_response("home", res)

        elif topic.endswith("/cmd/speed"):
            speed = payload.get("speed_mm_s", payload.get("speed", 25.0))
            res = self.service.set_speed(float(speed))
            self.publish_response("speed", res)

        elif topic.endswith("/cmd/clear_alarm"):
            res = self.service.clear_alarm()
            self.publish_response("clear_alarm", res)

    def publish_response(self, cmd: str, result: dict[str, Any]) -> None:
        if self.client and self.enabled:
            topic = f"{self.prefix}/response"
            payload = json.dumps({"cmd": cmd, "result": result})
            self.client.publish(topic, payload, qos=1)

    def publish_status(self) -> None:
        if self.client and self.enabled:
            topic = f"{self.prefix}/status"
            status_data = self.service.status_payload()
            self.client.publish(topic, json.dumps(status_data), qos=1, retain=True)
