"""Unit tests for MQTTService.

Covers:
- Environment variable precedence over file config
- TLS env vars are read and applied correctly
- rc=4/5 connection rejection shows auth/authz failure text
- Exponential reconnect backoff increments on repeated disconnects
- status_payload never exposes private key content
- Token/password sanitization in received messages
- Disabled service does not connect
"""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from narit_vending.mqtt_service import (
    MQTTService,
    _BACKOFF_INITIAL_S,
    _BACKOFF_MAX_S,
    _RC_REASON,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _disabled_service(**extra_config: object) -> MQTTService:
    """Return a disabled MQTTService with no paho client."""
    cfg = {"enabled": False, "cabinet_id": "CAB-TEST", **extra_config}
    with patch("narit_vending.mqtt_service.mqtt", None):
        return MQTTService(config=cfg)


def _enabled_service_fake_client(**extra_config: object) -> tuple[MQTTService, MagicMock]:
    """Return a disabled-then-manually-enabled service with a fake paho client."""
    service = _disabled_service(**extra_config)
    fake = MagicMock()
    fake.subscriptions: list = []
    fake.publications: list = []
    fake.subscribe.side_effect = lambda topic, qos=0: fake.subscriptions.append((topic, qos))
    fake.publish.side_effect = lambda topic, payload, qos=0, retain=False: (
        fake.publications.append((topic, payload, qos, retain)),
        MagicMock(),
    )[1]
    service.enabled = True
    service.client = fake
    return service, fake


# ---------------------------------------------------------------------------
# Existing tests (preserved)
# ---------------------------------------------------------------------------

class TestEnvironmentPrecedence(unittest.TestCase):
    def test_environment_overrides_file_configuration(self) -> None:
        environment = {
            "NARIT_MQTT_ENABLED": "true",
            "NARIT_MQTT_BROKER": "mqtt.environment.test",
            "NARIT_MQTT_USERNAME": "operator",
            "NARIT_MQTT_PASSWORD": "secret",
        }
        with (
            patch.dict("os.environ", environment, clear=False),
            patch("narit_vending.mqtt_service.mqtt", None),
        ):
            service = MQTTService(config={"enabled": False, "broker": "mqtt.file.test"})

        self.assertTrue(service.enabled)
        self.assertEqual(service.config["broker"], "mqtt.environment.test")
        self.assertEqual(service.config["username"], "operator")

    def test_disabled_legacy_config_does_not_require_cabinet_id_or_connect(self) -> None:
        service = MQTTService(
            config={
                "enabled": False,
                "client_id": "vending_machine_01",
                "topic_prefix": "vending/machine_01",
            }
        )
        service.start()
        self.assertFalse(service.enabled)
        self.assertEqual(service.cabinet_id, "CAB-001")
        self.assertIsNone(service.client)

    def test_monitor_telemetry_tracks_connection_and_redacts_received_token(self) -> None:
        service = _disabled_service()
        service.enabled = True

        class FakeClient:
            def __init__(self) -> None:
                self.subscriptions: list = []
                self.publications: list = []

            def subscribe(self, topic: str, qos: int = 0) -> None:
                self.subscriptions.append((topic, qos))

            def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False) -> MagicMock:
                self.publications.append((topic, payload, qos, retain))
                return MagicMock()

        client = FakeClient()
        service.client = client
        service._on_connect(client, None, {}, 0)
        message = SimpleNamespace(
            topic=service.T_COMMAND,
            payload=b'{"action":"ignored","scanned_token":"private-token"}',
            qos=1,
            retain=False,
        )
        service._on_message(client, None, message)
        status = service.status_payload()

        self.assertTrue(status["connected"])
        self.assertEqual(status["state"], "CONNECTED")
        self.assertEqual(status["received_count"], 1)
        self.assertEqual(status["rejected_count"], 1)
        self.assertEqual(status["messages"][0]["payload"]["scanned_token"], "***REDACTED***")
        self.assertEqual(client.subscriptions, [(service.T_COMMAND, 1)])


# ---------------------------------------------------------------------------
# New tests: TLS env vars
# ---------------------------------------------------------------------------

class TestTLSConfiguration(unittest.TestCase):
    def test_tls_env_vars_are_read_into_config(self) -> None:
        env = {
            "NARIT_MQTT_TLS_ENABLED": "true",
            "NARIT_MQTT_CA_CERT": "/etc/certs/ca.crt",
            "NARIT_MQTT_CLIENT_CERT": "/etc/certs/client.crt",
            "NARIT_MQTT_CLIENT_KEY": "/etc/certs/client.key",
            "NARIT_MQTT_TLS_INSECURE": "false",
        }
        with (
            patch.dict("os.environ", env, clear=False),
            patch("narit_vending.mqtt_service.mqtt", None),
        ):
            service = MQTTService(config={"enabled": False})

        self.assertTrue(service.config["tls_enabled"])
        self.assertEqual(service.config["tls_ca_cert"], "/etc/certs/ca.crt")
        self.assertEqual(service.config["tls_client_cert"], "/etc/certs/client.crt")
        self.assertEqual(service.config["tls_client_key"], "/etc/certs/client.key")
        self.assertFalse(service.config["tls_insecure"])

    def test_tls_insecure_defaults_to_false(self) -> None:
        with patch("narit_vending.mqtt_service.mqtt", None):
            service = MQTTService(config={"enabled": False})
        self.assertFalse(service.config["tls_insecure"])

    def test_status_payload_shows_tls_flags_without_exposing_key_path(self) -> None:
        service = _disabled_service(
            tls_enabled=True,
            tls_ca_cert="/etc/certs/ca.crt",
            tls_client_cert="/etc/certs/client.crt",
            tls_client_key="/etc/certs/client.key",
            tls_insecure=False,
        )
        status = service.status_payload()
        tls = status["broker"]["tls"]

        self.assertTrue(tls["enabled"])
        self.assertTrue(tls["ca_cert_configured"])
        self.assertTrue(tls["client_cert_configured"])
        self.assertTrue(tls["client_key_configured"])
        self.assertFalse(tls["insecure"])
        # Key path/content must NOT appear in status payload
        status_str = str(status)
        self.assertNotIn("client.key", status_str)

    def test_status_payload_no_tls_when_disabled(self) -> None:
        service = _disabled_service(tls_enabled=False)
        tls = service.status_payload()["broker"]["tls"]
        self.assertFalse(tls["enabled"])
        self.assertFalse(tls["client_key_configured"])


# ---------------------------------------------------------------------------
# New tests: rc=4/5 human-readable error messages
# ---------------------------------------------------------------------------

class TestConnectionRejectionMessages(unittest.TestCase):
    def _connect_with_rc(self, rc: int) -> str:
        """Trigger _on_connect with given rc, return last_error."""
        service, fake_client = _enabled_service_fake_client()
        service._on_connect(fake_client, None, {}, rc)
        return str(service.status_payload()["last_error"])

    def test_rc4_shows_authentication_failure(self) -> None:
        error = self._connect_with_rc(4)
        self.assertIn("authentication", error.lower())
        self.assertIn("rc=4", error)

    def test_rc5_shows_authorization_failure(self) -> None:
        error = self._connect_with_rc(5)
        self.assertIn("authorization", error.lower())
        self.assertIn("rc=5", error)

    def test_rc0_is_successful_connection(self) -> None:
        service, fake_client = _enabled_service_fake_client()
        service._on_connect(fake_client, None, {}, 0)
        self.assertTrue(service.status_payload()["connected"])
        self.assertEqual(service.status_payload()["state"], "CONNECTED")

    def test_rc_reason_table_covers_common_codes(self) -> None:
        for code in (1, 2, 3, 4, 5):
            self.assertIn(code, _RC_REASON, msg=f"rc={code} not in _RC_REASON")


# ---------------------------------------------------------------------------
# New tests: exponential reconnect backoff
# ---------------------------------------------------------------------------

class TestReconnectBackoff(unittest.TestCase):
    def test_backoff_increments_on_repeated_unexpected_disconnects(self) -> None:
        service, fake_client = _enabled_service_fake_client()
        # Simulate initial connect
        service._on_connect(fake_client, None, {}, 0)
        backoffs: list[float] = []

        for _ in range(5):
            service._on_disconnect(fake_client, None, 1)  # rc=1 → unexpected
            backoffs.append(float(service.status_payload()["reconnect_backoff_s"]))

        # Each successive disconnect must increase the backoff (until cap)
        for i in range(1, len(backoffs)):
            self.assertGreaterEqual(
                backoffs[i],
                backoffs[i - 1],
                msg=f"Backoff did not increase: {backoffs}",
            )

    def test_backoff_caps_at_max(self) -> None:
        service, fake_client = _enabled_service_fake_client()
        service._on_connect(fake_client, None, {}, 0)
        # Disconnect many times to exceed cap
        for _ in range(20):
            service._on_disconnect(fake_client, None, 1)
        backoff = float(service.status_payload()["reconnect_backoff_s"])
        self.assertLessEqual(backoff, _BACKOFF_MAX_S)

    def test_backoff_resets_on_successful_connect(self) -> None:
        service, fake_client = _enabled_service_fake_client()
        service._on_connect(fake_client, None, {}, 0)
        # Disconnect a few times to raise backoff
        for _ in range(4):
            service._on_disconnect(fake_client, None, 1)
        self.assertGreater(float(service.status_payload()["reconnect_backoff_s"]), _BACKOFF_INITIAL_S)
        # Reconnect successfully — backoff must reset
        service._on_connect(fake_client, None, {}, 0)
        self.assertEqual(float(service.status_payload()["reconnect_backoff_s"]), _BACKOFF_INITIAL_S)

    def test_clean_disconnect_does_not_increase_backoff(self) -> None:
        service, fake_client = _enabled_service_fake_client()
        service._on_connect(fake_client, None, {}, 0)
        service._on_disconnect(fake_client, None, 0)  # rc=0 = clean
        backoff = float(service.status_payload()["reconnect_backoff_s"])
        self.assertEqual(backoff, _BACKOFF_INITIAL_S)


# ---------------------------------------------------------------------------
# New tests: sanitization
# ---------------------------------------------------------------------------

class TestSanitization(unittest.TestCase):
    def test_password_redacted_in_received_message(self) -> None:
        service, fake_client = _enabled_service_fake_client()
        service._on_connect(fake_client, None, {}, 0)
        msg = SimpleNamespace(
            topic=service.T_COMMAND,
            payload=b'{"action":"ignored","password":"s3cr3t"}',
            qos=1,
            retain=False,
        )
        service._on_message(fake_client, None, msg)
        messages = service.status_payload()["messages"]
        self.assertEqual(messages[0]["payload"]["password"], "***REDACTED***")

    def test_config_password_not_in_status_payload(self) -> None:
        service = _disabled_service(username="user", password="hunter2")
        status_str = str(service.status_payload())
        self.assertNotIn("hunter2", status_str)


if __name__ == "__main__":
    unittest.main()
