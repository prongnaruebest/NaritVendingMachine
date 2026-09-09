import json
import os
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

os.environ["GPIOZERO_PIN_FACTORY"] = "mock"

from gpiozero import Device

from narit_vending.webapp import APIInputError, MotionService


ROOT = Path(__file__).resolve().parents[1]


class StartupSmokeTests(unittest.TestCase):
    def tearDown(self) -> None:
        Device.pin_factory.reset()

    def test_real_configuration_starts_on_mock_gpio_without_motion(self) -> None:
        service = MotionService(ROOT / "machine_config.json", ROOT / "hardware_config.json")

        health = service.health_payload()
        effective = service.effective_config_payload()

        self.assertTrue(health["service_ready"])
        self.assertFalse(health["machine_ready"])
        self.assertTrue(effective["valid"])
        self.assertEqual(effective["effective_axes"]["x"]["pulse_pin"], 16)
        self.assertEqual(effective["effective_axes"]["y"]["head_limit_pin"], 22)
        self.assertEqual(effective["effective_axes"]["z"]["enable_pin"], 19)
        routing = service.status_payload()["motion_profile_routing"]
        self.assertEqual(routing["x"]["move"]["route"], "legacy")
        self.assertTrue(routing["x"]["move"]["executable"])
        self.assertEqual(routing["z"]["home"]["route"], "legacy")

    def test_configuration_save_creates_restore_point_first(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            machine_path = root / "machine_config.json"
            hardware_path = root / "hardware_config.json"
            shutil.copy2(ROOT / "machine_config.json", machine_path)
            shutil.copy2(ROOT / "hardware_config.json", hardware_path)
            original_machine = machine_path.read_bytes()
            original_hardware = hardware_path.read_bytes()
            service = MotionService(machine_path, hardware_path)

            service.save_configuration(service.get_config())

            restore_points = list((root / "backups" / "config").iterdir())
            self.assertEqual(len(restore_points), 1)
            self.assertEqual((restore_points[0] / "machine_config.json").read_bytes(), original_machine)
            self.assertEqual((restore_points[0] / "hardware_config.json").read_bytes(), original_hardware)
            self.assertTrue((restore_points[0] / "manifest.json").exists())

    def test_configuration_save_preserves_disabled_xy_scurve_and_never_adds_it_to_z(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            machine_path = root / "machine_config.json"
            hardware_path = root / "hardware_config.json"
            machine = json.loads((ROOT / "machine_config.json").read_text(encoding="utf-8"))
            hardware = json.loads((ROOT / "hardware_config.json").read_text(encoding="utf-8"))
            fields = {
                "scurve_enabled": False,
                "scurve_profile_type": "seven_segment_s_curve",
                "scurve_start_speed_mm_s": 0.0,
                "scurve_end_speed_mm_s": 0.0,
                "scurve_max_jerk_mm_s3": 100.0,
                "scurve_control_period_us": 1000,
            }
            for axis in ("x", "y"):
                machine["axes"][axis]["commissioned_max_speed_mm_s"] = machine["axes"][axis]["max_speed_mm_s"]
                machine["axes"][axis].update(fields)
                hardware["machine_parameters"]["axes"][axis].update(fields)
            machine_path.write_text(json.dumps(machine), encoding="utf-8")
            hardware_path.write_text(json.dumps(hardware), encoding="utf-8")
            service = MotionService(machine_path, hardware_path)

            service.save_configuration(service.get_config())

            saved_machine = json.loads(machine_path.read_text(encoding="utf-8"))
            saved_hardware = json.loads(hardware_path.read_text(encoding="utf-8"))
            for axis in ("x", "y"):
                self.assertFalse(saved_machine["axes"][axis]["scurve_enabled"])
                self.assertEqual(saved_hardware["machine_parameters"]["axes"][axis]["scurve_control_period_us"], 1000)
            self.assertFalse(any(key.startswith("scurve_") for key in saved_machine["axes"]["z"]))

            unsafe = service.get_config()
            unsafe["axes"]["x"]["scurve_enabled"] = True
            with self.assertRaisesRegex(APIInputError, "handshake confirms"):
                service.save_configuration(unsafe)

    def test_manually_enabled_scurve_fails_closed_at_motion_entry_points(self) -> None:
        service = MotionService(ROOT / "machine_config.json", ROOT / "hardware_config.json")
        staged_x = replace(
            service.controller.config.x,
            scurve_enabled=True,
            scurve_profile_type="seven_segment_s_curve",
            scurve_start_speed_mm_s=0.0,
            scurve_end_speed_mm_s=0.0,
            scurve_max_jerk_mm_s3=100.0,
            scurve_control_period_us=1000,
        )
        service.controller.config = replace(service.controller.config, x=staged_x)

        results = (
            service.move_to(x_mm=1.0),
            service.jog("x", 1.0, allow_unhomed=True),
            service.home_axis("x"),
            service.move_to_limit("x", "max"),
            service.move_to_slot("1"),
        )

        for result in results:
            self.assertFalse(result["ok"])
            self.assertIn("blocked", result["error"])


if __name__ == "__main__":
    unittest.main()
