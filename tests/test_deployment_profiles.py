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
        self.assertTrue(mockup["self_contained"])
        self.assertTrue(v1["self_contained"])
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

    def test_each_profile_contains_deployable_application_code(self) -> None:
        for profile_name in ("NaritVendingMOCKUP", "NaritVendingV1"):
            profile = ROOT / profile_name
            for required in (
                "narit_vending/__init__.py",
                "narit_vending/webapp.py",
                "narit_vending/templates/index.html",
                "narit_vending/static/app.js",
                "deploy",
                "scripts",
                "tests",
                "main.py",
                "requirements.txt",
            ):
                self.assertTrue((profile / required).exists(), f"{profile_name}/{required} is missing")


if __name__ == "__main__":
    unittest.main()
