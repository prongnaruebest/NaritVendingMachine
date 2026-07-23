"""MQTT cabinet adapter with sanitized HMI monitoring telemetry."""

from __future__ import annotations

import json
import logging
import os
import ssl
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None


_log = logging.getLogger(__name__)

MQTT_CONFIG = {
    "enabled": False,
    "broker": "192.168.70.30",
    "port": 1883,
    "username": "",
    "password": "",
    "cabinet_id": "CAB-001",
    "keepalive_s": 20,
    # TLS defaults — all disabled unless explicitly enabled
    "tls_enabled": False,
    "tls_ca_cert": "",
    "tls_client_cert": "",
    "tls_client_key": "",
    "tls_insecure": False,
}

# Map rc codes to human-readable reasons
_RC_REASON: dict[int, str] = {
    0: "Connection accepted",
    1: "Connection refused — unacceptable protocol version (rc=1)",
    2: "Connection refused — client ID rejected (rc=2)",
    3: "Connection refused — broker unavailable (rc=3)",
    4: "Connection refused — authentication failure, check username/password (rc=4)",
    5: "Connection refused — authorization failure, check ACL/topic permissions (rc=5)",
}

# Exponential backoff caps
_BACKOFF_INITIAL_S = 2
_BACKOFF_MAX_S = 60


def _environment_config() -> dict[str, object]:
    values: dict[str, object] = {}
    mappings = {
        "broker": "NARIT_MQTT_BROKER",
        "username": "NARIT_MQTT_USERNAME",
        "password": "NARIT_MQTT_PASSWORD",
        "cabinet_id": "NARIT_MQTT_CABINET_ID",
        "tls_ca_cert": "NARIT_MQTT_CA_CERT",
        "tls_client_cert": "NARIT_MQTT_CLIENT_CERT",
        "tls_client_key": "NARIT_MQTT_CLIENT_KEY",
    }
    for key, variable in mappings.items():
        if variable in os.environ:
            values[key] = os.environ[variable]
    bool_vars = {
        "enabled": "NARIT_MQTT_ENABLED",
        "tls_enabled": "NARIT_MQTT_TLS_ENABLED",
        "tls_insecure": "NARIT_MQTT_TLS_INSECURE",
    }
    for key, variable in bool_vars.items():
        if variable in os.environ:
            values[key] = os.environ[variable].lower() in {"1", "true", "yes", "on"}
    if "NARIT_MQTT_PORT" in os.environ:
        values["port"] = int(os.environ["NARIT_MQTT_PORT"])
    if "NARIT_MQTT_KEEPALIVE_S" in os.environ:
        values["keepalive_s"] = int(os.environ["NARIT_MQTT_KEEPALIVE_S"])
    return values


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_payload(value: object) -> object:
    secret_keys = {
        "password",
        "passwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "scanned_token",
    }
    if isinstance(value, dict):
        return {
            str(key): "***REDACTED***" if str(key).lower() in secret_keys else _sanitize_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_payload(item) for item in value]
    return value


class SimMotor:
    def start_motion(self, slot: object) -> dict[str, object]:
        _log.info("SimMotor: dispensing slot %s", slot)
        time.sleep(1.5)
        return {
            "ok": True,
            "sensor_confirmed": True,
            "state_trace": ["moving", "picking", "delivering", "confirming"],
        }


class MQTTService:
    def __init__(self, motion_service: object | None = None, config: dict[str, Any] | None = None) -> None:
        supplied_config = dict(config or {})
        self.config = MQTT_CONFIG | supplied_config | _environment_config()
        self.service = motion_service or SimMotor()
        self.enabled = bool(self.config.get("enabled", False))
        self.cabinet_id = str(self.config.get("cabinet_id") or MQTT_CONFIG["cabinet_id"])

        prefix = f"cabinet/{self.cabinet_id}"
        self.T_SCAN = f"{prefix}/scan"
        self.T_COMMAND = f"{prefix}/command"
        self.T_STATUS = f"{prefix}/status"
        self.T_PRESENCE = f"{prefix}/presence"

        self._done: dict[str, object] = {}
        self.client: Any = None
        self._telemetry_lock = threading.RLock()
        self._messages: deque[dict[str, object]] = deque(maxlen=100)
        self._backoff_s: float = _BACKOFF_INITIAL_S
        self._telemetry: dict[str, object] = {
            "state": "DISABLED" if not self.enabled else "INITIALIZING",
            "connected": False,
            "started_at": None,
            "connected_at": None,
            "disconnected_at": None,
            "last_message_at": None,
            "last_publish_at": None,
            "last_error": "",
            "connect_count": 0,
            "disconnect_count": 0,
            "received_count": 0,
            "published_count": 0,
            "command_count": 0,
            "rejected_count": 0,
            "reconnect_backoff_s": _BACKOFF_INITIAL_S,
        }

        if not self.enabled:
            _log.info("MQTT service is disabled in hardware_config.json")
            return
        if mqtt is None:
            self._set_telemetry(state="UNAVAILABLE", last_error="paho-mqtt is not installed")
            _log.warning("paho-mqtt is not installed; MQTT service will remain offline")
            return

        try:
            self.client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION1,
                client_id=self.cabinet_id,
                clean_session=False,
            )
        except (AttributeError, TypeError):
            self.client = mqtt.Client(client_id=self.cabinet_id, clean_session=False)

        if self.config.get("username"):
            self.client.username_pw_set(
                str(self.config["username"]),
                str(self.config.get("password", "")),
            )

        # ── TLS configuration ──────────────────────────────────────────────
        if self.config.get("tls_enabled"):
            self._apply_tls()

        self.client.will_set(
            self.T_PRESENCE,
            json.dumps({"state": "offline", "cabinet_id": self.cabinet_id, "timestamp": None}),
            qos=1,
            retain=True,
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    # ── TLS helpers ────────────────────────────────────────────────────────

    def _apply_tls(self) -> None:
        """Configure TLS on the paho client from stored config values.

        Certificate *paths* are logged at DEBUG but the key content is never
        logged, stored in telemetry, or included in API responses.
        """
        ca_cert = str(self.config.get("tls_ca_cert") or "") or None
        client_cert = str(self.config.get("tls_client_cert") or "") or None
        client_key = str(self.config.get("tls_client_key") or "") or None
        # Default to CERT_REQUIRED; only relax when explicitly insecure=true
        cert_reqs = ssl.CERT_NONE if self.config.get("tls_insecure") else ssl.CERT_REQUIRED
        tls_version = ssl.PROTOCOL_TLS_CLIENT if not self.config.get("tls_insecure") else ssl.PROTOCOL_TLS

        try:
            self.client.tls_set(
                ca_certs=ca_cert,
                certfile=client_cert,
                keyfile=client_key,
                cert_reqs=cert_reqs,
                tls_version=tls_version,
            )
            if self.config.get("tls_insecure"):
                self.client.tls_insecure_set(True)
                _log.warning("TLS hostname verification is DISABLED (tls_insecure=true)")
            _log.info(
                "TLS enabled: ca_cert=%s client_cert=%s insecure=%s",
                bool(ca_cert),
                bool(client_cert),
                self.config.get("tls_insecure"),
            )
        except Exception as exc:
            self._set_telemetry(state="ERROR", last_error=f"TLS setup failed: {exc}")
            _log.error("TLS setup error: %s", exc)
            raise

    # ── Telemetry helpers ──────────────────────────────────────────────────

    def _set_telemetry(self, **values: object) -> None:
        with self._telemetry_lock:
            self._telemetry.update(values)

    def _increment(self, field: str) -> None:
        with self._telemetry_lock:
            self._telemetry[field] = int(self._telemetry.get(field, 0)) + 1

    def _record_message(
        self,
        direction: str,
        topic: str,
        payload: object,
        *,
        qos: int = 0,
        retain: bool = False,
    ) -> None:
        timestamp = _now()
        with self._telemetry_lock:
            self._messages.appendleft(
                {
                    "timestamp": timestamp,
                    "direction": direction,
                    "topic": topic,
                    "qos": qos,
                    "retain": retain,
                    "payload": _sanitize_payload(payload),
                }
            )
            if direction == "RX":
                self._telemetry["last_message_at"] = timestamp
                self._telemetry["received_count"] = int(self._telemetry["received_count"]) + 1
            else:
                self._telemetry["last_publish_at"] = timestamp
                self._telemetry["published_count"] = int(self._telemetry["published_count"]) + 1

    def _publish(self, topic: str, payload: object, *, qos: int = 1, retain: bool = False) -> Any:
        if self.client is None:
            return None
        encoded = payload if isinstance(payload, str) else json.dumps(payload)
        result = self.client.publish(topic, encoded, qos=qos, retain=retain)
        try:
            recorded_payload = json.loads(encoded)
        except (TypeError, json.JSONDecodeError):
            recorded_payload = {"payload_bytes": len(str(encoded).encode("utf-8"))}
        self._record_message("TX", topic, recorded_payload, qos=qos, retain=retain)
        return result

    # ── Public API ─────────────────────────────────────────────────────────

    def status_payload(self) -> dict[str, object]:
        with self._telemetry_lock:
            telemetry = dict(self._telemetry)
            messages = list(self._messages)
        tls_status: dict[str, object] = {
            "enabled": bool(self.config.get("tls_enabled")),
            "ca_cert_configured": bool(self.config.get("tls_ca_cert")),
            "client_cert_configured": bool(self.config.get("tls_client_cert")),
            # NOTE: never expose key path or key content
            "client_key_configured": bool(self.config.get("tls_client_key")),
            "insecure": bool(self.config.get("tls_insecure")),
        }
        return {
            "enabled": self.enabled,
            "client_available": self.client is not None,
            "broker": {
                "host": str(self.config.get("broker", "")),
                "port": int(self.config.get("port", 1883)),
                "keepalive_s": int(self.config.get("keepalive_s", 20)),
                "authentication_configured": bool(self.config.get("username")),
                "tls": tls_status,
            },
            "client": {"cabinet_id": self.cabinet_id, "clean_session": False},
            "topics": {
                "subscribe": [self.T_COMMAND],
                "publish": [self.T_SCAN, self.T_STATUS, self.T_PRESENCE],
            },
            **telemetry,
            "messages": messages,
            "timestamp": _now(),
        }

    def start(self) -> None:
        if not self.enabled or self.client is None:
            return
        broker = str(self.config.get("broker", "127.0.0.1"))
        port = int(self.config.get("port", 1883))
        keepalive = int(self.config.get("keepalive_s", 20))
        self._backoff_s = _BACKOFF_INITIAL_S
        self._set_telemetry(
            state="CONNECTING",
            started_at=_now(),
            last_error="",
            reconnect_backoff_s=self._backoff_s,
        )
        _log.info("connecting to broker %s:%d as %s", broker, port, self.cabinet_id)
        try:
            self.client.connect_async(broker, port, keepalive=keepalive)
            self.client.loop_start()
        except Exception as exc:
            self._set_telemetry(state="ERROR", last_error=str(exc))
            _log.error("MQTT connection startup failed: %s", exc)

    def stop(self) -> None:
        if not self.enabled or self.client is None:
            return
        info = self._publish_presence("offline")
        try:
            if info is not None:
                info.wait_for_publish(timeout=2.0)
        except Exception:
            pass
        self.client.loop_stop()
        self.client.disconnect()
        self._set_telemetry(state="STOPPED", connected=False, disconnected_at=_now())

    # ── MQTT callbacks ─────────────────────────────────────────────────────

    def _on_connect(self, client: Any, userdata: Any, flags: Any, rc: int) -> None:
        if rc != 0:
            reason = _RC_REASON.get(rc, f"Connection rejected (rc={rc})")
            self._set_telemetry(state="ERROR", connected=False, last_error=reason)
            _log.error("MQTT %s", reason)
            return
        # Successful connection — reset backoff
        self._backoff_s = _BACKOFF_INITIAL_S
        self._increment("connect_count")
        self._set_telemetry(
            state="CONNECTED",
            connected=True,
            connected_at=_now(),
            last_error="",
            reconnect_backoff_s=self._backoff_s,
        )
        client.subscribe(self.T_COMMAND, qos=1)
        self._publish_presence("online")

    def _on_disconnect(self, client: Any, userdata: Any, rc: int) -> None:
        self._increment("disconnect_count")
        if rc == 0:
            error = ""
            new_state = "DISCONNECTED"
        else:
            reason = _RC_REASON.get(rc, f"rc={rc}")
            error = f"Unexpected disconnect ({reason})"
            new_state = "CONNECTION_LOST"

        # Exponential backoff — cap at _BACKOFF_MAX_S
        if rc != 0:
            self._backoff_s = min(self._backoff_s * 2, _BACKOFF_MAX_S)
        else:
            self._backoff_s = _BACKOFF_INITIAL_S

        self._set_telemetry(
            state=new_state,
            connected=False,
            disconnected_at=_now(),
            last_error=error,
            reconnect_backoff_s=self._backoff_s,
        )
        if error:
            _log.warning(error)

    def _on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        raw_payload = msg.payload.decode("utf-8", errors="replace") if msg.payload else ""
        try:
            command = json.loads(raw_payload)
        except Exception:
            self._record_message(
                "RX",
                str(msg.topic),
                {"parse_error": "Invalid JSON", "payload_bytes": len(msg.payload or b"")},
                qos=int(msg.qos),
                retain=bool(msg.retain),
            )
            self._increment("rejected_count")
            self._set_telemetry(last_error="Invalid JSON command payload")
            return

        self._record_message("RX", str(msg.topic), command, qos=int(msg.qos), retain=bool(msg.retain))
        self._set_telemetry(last_error="")
        if command.get("action") != "release":
            self._increment("rejected_count")
            return

        self._increment("command_count")
        request_id = command.get("request_id")
        if not request_id:
            self._increment("rejected_count")
            self._status(None, command, "failed", reason="MISSING_REQUEST_ID", final=True)
            return

        if request_id in self._done:
            previous = self._done[request_id]
            if isinstance(previous, dict):
                self._publish(self.T_STATUS, previous, qos=1)
            return

        expires_at = command.get("expires_at")
        if expires_at and str(expires_at) < _now():
            self._increment("rejected_count")
            self._status(request_id, command, "failed", reason="COMMAND_EXPIRED", final=True)
            return
        if command.get("slot") is None:
            self._increment("rejected_count")
            self._status(request_id, command, "failed", reason="NO_TARGET", final=True)
            return

        self._status(request_id, command, "received")
        self._done[request_id] = "processing"
        try:
            result = self.service.start_motion(command.get("slot"))
            ok = bool(result.get("ok"))
            self._status(
                request_id,
                command,
                "success" if ok else "failed",
                sensor_confirmed=result.get("sensor_confirmed"),
                state_trace=result.get("state_trace"),
                reason=None if ok else "DROP_NOT_DETECTED",
                final=True,
            )
        except Exception:
            _log.exception("motor error")
            self._status(request_id, command, "failed", reason="MOTOR_EXCEPTION", final=True)

    def _publish_presence(self, state: str) -> Any:
        if self.client is None:
            return None
        info = self._publish(
            self.T_PRESENCE,
            {"state": state, "cabinet_id": self.cabinet_id, "timestamp": _now()},
            qos=1,
            retain=True,
        )
        _log.info("presence -> %s", state)
        return info

    def _status(
        self,
        request_id: object,
        command: dict[str, object],
        state: str,
        reason: str | None = None,
        sensor_confirmed: object | None = None,
        state_trace: object | None = None,
        final: bool = False,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "request_id": request_id,
            "order_id": command.get("order_id"),
            "state": state,
            "slot": command.get("slot"),
            "timestamp": _now(),
        }
        if reason is not None:
            payload["reason"] = reason
        if sensor_confirmed is not None:
            payload["sensor_confirmed"] = sensor_confirmed
        if state_trace is not None:
            payload["state_trace"] = state_trace
        if final and request_id:
            self._done[str(request_id)] = payload
        self._publish(self.T_STATUS, payload, qos=1)
        return payload

    def publish_scan(self, token: str) -> bool:
        if not self.enabled or self.client is None:
            _log.warning("scan ignored because MQTT is disabled or unavailable")
            return False
        payload = {
            "request_id": f"scan-{uuid.uuid4().hex[:6]}",
            "cabinet_id": self.cabinet_id,
            "scanned_token": token,
            "scanned_at": _now(),
        }
        self._publish(self.T_SCAN, payload, qos=1)
        return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [Pi] %(message)s")
    service = MQTTService()
    if not service.enabled:
        raise SystemExit("MQTT is disabled. Set NARIT_MQTT_ENABLED=true before standalone testing.")
    service.start()
    try:
        while True:
            line = input().strip()
            if line.lower() in ("q", "quit", "exit"):
                break
            if line:
                service.publish_scan(line)
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        service.stop()
