from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "narit_vending" / "templates" / "index.html").read_text(encoding="utf-8")
APP_JS = (ROOT / "narit_vending" / "static" / "app.js").read_text(encoding="utf-8")
STYLE = (ROOT / "narit_vending" / "static" / "style.css").read_text(encoding="utf-8")


class FrontendAcceptanceTests(unittest.TestCase):
    def test_every_required_workspace_has_navigation_and_deep_link_support(self) -> None:
        required = {
            "dashboard", "motion", "slots", "visualization", "diagnostics", "io-status",
            "alarms", "events", "flow", "sequence-monitor", "architecture", "configuration",
            "motor-test", "mqtt",
        }
        pages = set(re.findall(r'data-view-page="([^"]+)"', TEMPLATE))
        targets = set(re.findall(r'data-view-target="([^"]+)"', TEMPLATE))
        match = re.search(r"const VALID_VIEWS = new Set\(\[(.*?)\]\);", APP_JS, re.S)
        self.assertIsNotNone(match)
        valid_views = set(re.findall(r'"([^"]+)"', match.group(1)))
        self.assertTrue(required <= pages)
        self.assertTrue(required <= targets)
        self.assertTrue(required <= valid_views)
        self.assertIn('window.addEventListener("hashchange"', APP_JS)

    def test_javascript_functions_are_declared_once(self) -> None:
        names = re.findall(r"^\s*function\s+([A-Za-z_$][\w$]*)\s*\(", APP_JS, re.M)
        duplicates = sorted({name for name in names if names.count(name) > 1})
        self.assertEqual(duplicates, [], f"Duplicate JavaScript functions: {duplicates}")

    def test_structural_icons_do_not_use_emoji(self) -> None:
        forbidden = set("🛑🔄⚠️🔓⚡🔍✅❌🖐️⚙")
        self.assertEqual(sorted(forbidden.intersection(TEMPLATE + APP_JS)), [])

    def test_linked_axis_speed_controls_use_shared_state(self) -> None:
        self.assertGreaterEqual(TEMPLATE.count("data-axis-speed-bank"), 6)
        self.assertIn("axisSpeeds: { x: 5.0, y: 5.0, z: 5.0 }", APP_JS)
        self.assertIn('localStorage.setItem("narit.axisSpeeds"', APP_JS)
        self.assertIn("effectiveMotionSpeed([axis])", APP_JS)
        self.assertIn('invalidateMotionWorkflow("Axis speed changed', APP_JS)

    def test_manual_commissioning_frequency_tracks_protocol_capability(self) -> None:
        self.assertIn("function motorTestFrequencyCap()", APP_JS)
        self.assertIn("protocol || 1) >= 3 ? 50000 : 1000", APP_JS)
        self.assertNotIn("Math.min(1000, Number.isFinite(freqVal)", APP_JS)

    def test_mobile_navigation_remains_accessible(self) -> None:
        self.assertIn('grid-template-areas:"header" "sidebar" "workspace" "footer"', STYLE)
        self.assertIn(".sidebar { display: block !important", STYLE)
        self.assertIn("overflow-x: auto", STYLE)

    def test_no_inline_javascript_navigation(self) -> None:
        self.assertNotIn("onclick=", TEMPLATE)
        self.assertNotIn("javascript:", TEMPLATE.lower())

    def test_homing_replaces_feed_override_in_motion_and_system_control_follows_overview(self) -> None:
        self.assertNotIn('data-view-page="homing"', TEMPLATE)
        self.assertNotIn('id="nav-homing-controls"', TEMPLATE)
        self.assertNotIn('data-homing-shortcut', TEMPLATE)
        self.assertIn('data-view-page="motion"', TEMPLATE)
        self.assertEqual(TEMPLATE.count('id="homing-controls"'), 1)
        self.assertEqual(TEMPLATE.count('id="home-all"'), 1)
        self.assertNotIn('class="feed-override-card"', TEMPLATE)
        self.assertNotIn('Feed Rate Override (Next Command)', TEMPLATE)
        self.assertIn('grid-template-columns: minmax(0, 1fr) !important', STYLE)
        self.assertLess(TEMPLATE.index('id="nav-dashboard"'), TEMPLATE.index('id="nav-system-control"'))
        self.assertLess(TEMPLATE.index('id="nav-system-control"'), TEMPLATE.index('id="nav-motion"'))

    def test_speed_change_rechecks_direct_motion_without_reusing_goto_arm(self) -> None:
        self.assertIn("updateButtonStates();", APP_JS)
        self.assertIn("Speed is a next-command parameter", APP_JS)
        self.assertIn("validate, preview and arm the GOTO command again", APP_JS)
        self.assertIn('button.title = reason ||', APP_JS)
        self.assertIn("The axis is ready for the next Min/Max or Jog command", APP_JS)


if __name__ == "__main__":
    unittest.main()
