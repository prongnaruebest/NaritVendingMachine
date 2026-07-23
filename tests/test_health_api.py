import unittest
from unittest.mock import patch

from narit_vending.webapp import create_app


class FakeMQTTService:
    def status_payload(self) -> dict[str, object]:
        return {
            "enabled": True,
            "connected": True,
            "state": "CONNECTED",
            "broker": {"host": "mqtt.example.test", "port": 1883},
            "messages": [],
        }


class FakeMotionService:
    def __init__(self, config_path: str, hw_config_path: str) -> None:
        self.config_path = config_path
        self.hw_config_path = hw_config_path
        self.mqtt_service = FakeMQTTService()

    def health_payload(self) -> dict[str, object]:
        return {
            "status": "UP",
            "service_ready": True,
            "machine_ready": False,
            "machine_state": "not_ready",
            "config_revision": "test-revision",
            "config_valid": True,
            "timestamp": "2026-01-01T00:00:00+00:00",
        }

    def effective_config_payload(self) -> dict[str, object]:
        return {"valid": True, "revision": "test-revision", "issues": []}


class HealthApiTests(unittest.TestCase):
    def setUp(self) -> None:
        patcher = patch("narit_vending.webapp.MotionService", FakeMotionService)
        patcher.start()
        self.addCleanup(patcher.stop)
        app = create_app("machine.json", "hardware.json")
        app.testing = True
        self.client = app.test_client()

    def test_liveness_does_not_depend_on_machine_homing(self) -> None:
        response = self.client.get("/health/live")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "UP")

    def test_readiness_distinguishes_service_from_machine(self) -> None:
        response = self.client.get("/health/ready")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["service_ready"])
        self.assertFalse(response.get_json()["machine_ready"])

    def test_effective_config_endpoint_exposes_revision(self) -> None:
        response = self.client.get("/api/config/effective")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["revision"], "test-revision")

    def test_hmi_shell_keeps_all_workspace_sections(self) -> None:
        response = self.client.get("/")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        for workspace in ("dashboard", "motion", "visualization", "slots", "diagnostics", "configuration", "mqtt", "alarms", "events", "flow"):
            self.assertIn(f'data-view-target="{workspace}"', html)

    def test_mqtt_monitor_endpoint_returns_connection_telemetry(self) -> None:
        response = self.client.get("/api/mqtt/status")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["connected"])
        self.assertEqual(payload["state"], "CONNECTED")
        self.assertEqual(payload["broker"]["host"], "mqtt.example.test")


class WebAppNewProcessTests(unittest.TestCase):
    def test_new_web_app_index_renders_template(self) -> None:
        from unittest.mock import MagicMock
        from narit_vending.web.app import create_web_app

        mock_ctrl = MagicMock()
        app = create_web_app(mock_ctrl)
        app.testing = True
        client = app.test_client()

        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("NARIT VENDING", html)


if __name__ == "__main__":
    unittest.main()
