import unittest
from pathlib import Path
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
        self.assertIn('id="visual-home-all"', html)
        for element_id in (
            "slot-summary-total", "slot-summary-ready", "slot-summary-empty",
            "slot-summary-invalid", "slot-summary-selected", "slot-detail-status",
        ):
            self.assertIn(f'id="{element_id}"', html)
        for status in ("not-configured", "invalid", "alarm"):
            self.assertIn(f'value="{status}"', html)
        for element_id in (
            "event-total-count", "event-fault-count", "event-warn-count",
            "event-search", "event-category-filter", "event-detail-content",
            "sidebar-device-label", "hdr-device",
        ):
            self.assertIn(f'id="{element_id}"', html)

    def test_hmi_labels_legacy_mockup_and_new_iriv_devices(self) -> None:
        app_js = (Path(__file__).resolve().parents[1] / "narit_vending" / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("อุปกรณ์เก่า · Raspberry Pi Mockup", app_js)
        self.assertIn("อุปกรณ์ใหม่ · IRIV (เตรียมใช้งานจริง)", app_js)
        self.assertIn('isIriv ? "NEW · IRIV" : "OLD · MOCKUP"', app_js)

    def test_mqtt_monitor_endpoint_returns_connection_telemetry(self) -> None:
        response = self.client.get("/api/mqtt/status")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["connected"])
        self.assertEqual(payload["state"], "CONNECTED")
        self.assertEqual(payload["broker"]["host"], "mqtt.example.test")

    def test_slot_manager_keeps_position_and_confirmation_guards(self) -> None:
        app_js = (Path(__file__).resolve().parents[1] / "narit_vending" / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("slotAtCurrentPosition(slot)", app_js)
        self.assertIn("const canDispense = validSlot && canMove && slotAtCurrentPosition(slot);", app_js)
        self.assertIn("if (!window.confirm(confirmation)) return;", app_js)

    def test_alarm_page_sorts_fault_warning_and_normal_states(self) -> None:
        app_js = (Path(__file__).resolve().parents[1] / "narit_vending" / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('channel.level === "fault" ? 0 : 1', app_js)
        self.assertIn("orderedAlarms", app_js)
        self.assertIn('faultCount > 0 ? "fault" : (warningCount > 0 ? "warn" : "clear")', app_js)

    def test_event_history_has_safe_sort_filter_and_detail_guards(self) -> None:
        app_js = (Path(__file__).resolve().parents[1] / "narit_vending" / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("function sanitizeEventText", app_js)
        self.assertIn("function sortedEvents", app_js)
        self.assertIn("eventPriority(a) - eventPriority(b)", app_js)
        self.assertIn("renderEventDetail", app_js)
        self.assertIn("This page never sends a machine command", app_js)

    def test_system_flow_has_interlock_priority_and_read_only_detail(self) -> None:
        app_js = (Path(__file__).resolve().parents[1] / "narit_vending" / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('blocked.push(["E-STOP"', app_js)
        self.assertIn('blocked.push(["ACTIVE ALARM"', app_js)
        self.assertIn('blocked.push(["CONTROLLER OFFLINE"', app_js)
        self.assertIn('setFlow("flow-complete"', app_js)
        self.assertIn("No machine command is sent from this panel", app_js)


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

    def test_mqtt_runtime_control_endpoint(self) -> None:
        from unittest.mock import MagicMock
        from narit_vending.web.app import create_web_app

        mock_ctrl = MagicMock()
        mock_ctrl.mqtt_control.return_value = {
            "enabled": True,
            "runtime_enabled": False,
            "connected": False,
            "state": "STOPPED",
        }
        app = create_web_app(mock_ctrl)
        app.testing = True

        response = app.test_client().post("/api/mqtt/control", json={"action": "disconnect"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])
        mock_ctrl.mqtt_control.assert_called_once_with(False)


if __name__ == "__main__":
    unittest.main()
