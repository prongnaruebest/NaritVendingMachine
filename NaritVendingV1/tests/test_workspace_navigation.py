import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkspaceNavigationTests(unittest.TestCase):
    def test_only_active_io_status_page_is_displayed(self) -> None:
        stylesheet = (ROOT / "narit_vending" / "static" / "style.css").read_text(
            encoding="utf-8"
        )

        io_page_rule = re.search(
            r"\.workspace-view\.io-status-page\s*\{(?P<body>.*?)\}",
            stylesheet,
            re.DOTALL,
        )
        active_io_page_rule = re.search(
            r"\.workspace-view\.io-status-page\.active\s*\{(?P<body>.*?)\}",
            stylesheet,
            re.DOTALL,
        )

        self.assertIsNotNone(io_page_rule)
        self.assertNotIn("display:", io_page_rule.group("body"))
        self.assertIsNotNone(active_io_page_rule)
        self.assertRegex(active_io_page_rule.group("body"), r"display:\s*flex")
        self.assertRegex(active_io_page_rule.group("body"), r"overflow-y:\s*auto")

    def test_web_interface_contains_no_thai_text(self) -> None:
        thai_text = re.compile(r"[\u0e00-\u0e7f]")
        web_files = [
            ROOT / "narit_vending" / "templates" / "index.html",
            ROOT / "narit_vending" / "static" / "app.js",
        ]

        for web_file in web_files:
            with self.subTest(web_file=web_file.name):
                contents = web_file.read_text(encoding="utf-8")
                self.assertIsNone(thai_text.search(contents))

    def test_motor_test_long_burst_limits_match_controller_protocol(self) -> None:
        template = (ROOT / "narit_vending" / "templates" / "index.html").read_text(
            encoding="utf-8"
        )
        script = (ROOT / "narit_vending" / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        controller = (ROOT / "narit_vending" / "webapp.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('id="motor-test-pulses" type="number" min="1" max="10000"', template)
        self.assertIn("parameters.pulses <= 10000", script)
        self.assertIn("duration <= 10", script)
        self.assertIn("MOTOR_TEST_MAX_DURATION_S = 10.0", controller)
        self.assertIn("MOTOR_TEST_MAX_PULSES = 10_000", controller)

    def test_iriv_configuration_save_preserves_locked_hardware(self) -> None:
        script = (ROOT / "narit_vending" / "static" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('JSON.parse(JSON.stringify(MS.config?.hardware || {}))', script)
        self.assertIn("hardware.motors ||= {}", script)
        self.assertNotIn(
            "const hardware = { motors: {}, digital_inputs: {}, digital_outputs: {} };",
            script,
        )

    def test_configuration_apply_waits_for_controller_config_reload(self) -> None:
        script = (ROOT / "narit_vending" / "static" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            'const config = await apiCall("/api/config", "GET", undefined, 1500);',
            script,
        )
        self.assertIn(
            "if (config.axes && config.hardware && config.restart_required === false)",
            script,
        )
        self.assertNotIn(
            'await apiCall("/api/ping", "GET", undefined, 1500);', script
        )

    def test_controller_services_restart_after_configuration_apply(self) -> None:
        for unit_name in (
            "narit-vending-controller.service",
            "narit-vending-controller-iriv.service",
        ):
            unit = (ROOT / "deploy" / unit_name).read_text(encoding="utf-8")
            self.assertIn("Restart=always", unit)


if __name__ == "__main__":
    unittest.main()
