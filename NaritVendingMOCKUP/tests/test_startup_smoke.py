import os
import shutil
import tempfile
import unittest
from pathlib import Path

os.environ["GPIOZERO_PIN_FACTORY"] = "mock"

from gpiozero import Device

from narit_vending.webapp import MotionService


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


if __name__ == "__main__":
    unittest.main()
