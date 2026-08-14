from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DeploymentProfileTests(unittest.TestCase):
    def test_mockup_and_v1_profiles_are_separate(self) -> None:
        mockup = json.loads((ROOT / "NaritVendingMOCKUP" / "profile.json").read_text(encoding="utf-8"))
        v1 = json.loads((ROOT / "NaritVendingV1" / "profile.json").read_text(encoding="utf-8"))

        self.assertEqual(mockup["name"], "MOCKUP")
        self.assertEqual(v1["name"], "V1")
        self.assertNotEqual(mockup["remote_dir"], v1["remote_dir"])
        self.assertEqual(mockup["remote_dir"], "/home/admin/NaritVendingMOCKUP")
        self.assertEqual(v1["remote_dir"], "/home/admin/NaritVendingV1")

    def test_systemd_units_use_profile_paths(self) -> None:
        mockup_units = "\n".join(
            (ROOT / "deploy" / name).read_text(encoding="utf-8")
            for name in ("narit-vending-controller.service", "narit-vending-web.service")
        )
        v1_units = "\n".join(
            (ROOT / "deploy" / name).read_text(encoding="utf-8")
            for name in ("narit-vending-controller-iriv.service", "narit-vending-web-iriv.service")
        )

        self.assertIn("/home/admin/NaritVendingMOCKUP", mockup_units)
        self.assertNotIn("/home/admin/NaritVendingV1", mockup_units)
        self.assertIn("/home/admin/NaritVendingV1", v1_units)
        self.assertNotIn("/home/admin/NaritVendingMOCKUP", v1_units)


if __name__ == "__main__":
    unittest.main()
