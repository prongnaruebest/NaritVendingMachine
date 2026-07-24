import copy
import json
import tempfile
import unittest
from pathlib import Path

from narit_vending.config_foundation import (
    create_config_backup,
    restore_config_backup,
    validate_configuration_files,
    validate_configuration_payloads,
)


ROOT = Path(__file__).resolve().parents[1]


class ConfigFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.machine = json.loads((ROOT / "machine_config.json").read_text(encoding="utf-8"))
        self.hardware = json.loads((ROOT / "hardware_config.json").read_text(encoding="utf-8"))

    def test_current_configuration_is_valid_and_reports_effective_values(self) -> None:
        report = validate_configuration_files(ROOT / "machine_config.json", ROOT / "hardware_config.json")

        self.assertTrue(report.valid)
        self.assertEqual(report.effective_axes["x"]["pulse_pin"], 16)
        self.assertEqual(report.effective_axes["y"]["head_limit_pin"], 9)
        self.assertEqual(report.effective_axes["y"]["tail_limit_pin"], 22)
        self.assertEqual(len(report.revision), 64)

    def test_duplicate_output_pin_is_rejected(self) -> None:
        hardware = copy.deepcopy(self.hardware)
        hardware["digital_outputs"]["alarm_buzzer"]["pin"] = hardware["motors"]["x"]["step_pin"]

        report = validate_configuration_payloads(self.machine, hardware)

        self.assertFalse(report.valid)
        self.assertTrue(any(issue.code == "GPIO_PIN_COLLISION" for issue in report.issues))

    def test_home_sensor_and_head_limit_alias_is_allowed(self) -> None:
        report = validate_configuration_payloads(self.machine, self.hardware)

        collisions = [issue for issue in report.issues if issue.code == "GPIO_PIN_COLLISION"]
        self.assertEqual(collisions, [])

    def test_backup_contains_manifest_and_original_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            machine_path = root / "machine.json"
            hardware_path = root / "hardware.json"
            machine_path.write_text(json.dumps(self.machine), encoding="utf-8")
            hardware_path.write_text(json.dumps(self.hardware), encoding="utf-8")

            backup = create_config_backup((machine_path, hardware_path), root / "backups", reason="test")

            self.assertEqual((backup / "machine.json").read_bytes(), machine_path.read_bytes())
            manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["reason"], "test")
            self.assertEqual(len(manifest["files"]), 2)

    def test_restore_verifies_and_recovers_both_config_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            machine_path = root / "machine.json"
            hardware_path = root / "hardware.json"
            machine_path.write_text(json.dumps(self.machine), encoding="utf-8")
            hardware_path.write_text(json.dumps(self.hardware), encoding="utf-8")
            expected_machine = machine_path.read_bytes()
            expected_hardware = hardware_path.read_bytes()
            backup = create_config_backup((machine_path, hardware_path), root / "backups", reason="rollback-test")
            machine_path.write_text("{}", encoding="utf-8")
            hardware_path.write_text("{}", encoding="utf-8")

            restored = restore_config_backup(
                backup,
                {"machine.json": machine_path, "hardware.json": hardware_path},
            )

            self.assertEqual(set(restored), {machine_path, hardware_path})
            self.assertEqual(machine_path.read_bytes(), expected_machine)
            self.assertEqual(hardware_path.read_bytes(), expected_hardware)


if __name__ == "__main__":
    unittest.main()
