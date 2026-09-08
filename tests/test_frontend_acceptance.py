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
        self.assertGreaterEqual(TEMPLATE.count("data-axis-speed-bank"), 4)
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

    def test_slots_uses_the_page_scroll_like_visualization(self) -> None:
        self.assertIn('data-view-page="slots"', TEMPLATE)
        self.assertIn('.workspace-view[data-view-page="slots"] .slot-table-wrap', STYLE)
        self.assertIn('height: auto !important', STYLE)
        self.assertIn("max-height: none", STYLE)
        self.assertIn("overflow-y: visible !important", STYLE)
        self.assertIn("overscroll-behavior: auto !important", STYLE)

    def test_slot_polling_does_not_replace_an_active_coordinate_editor(self) -> None:
        self.assertIn("coordinateEditorActive", APP_JS)
        self.assertIn("tbody.contains(document.activeElement)", APP_JS)
        self.assertIn("tbody.dataset.renderSignature === renderSignature", APP_JS)

    def test_live_axis_positions_are_persistent_across_workspaces(self) -> None:
        for axis in ("x", "y", "z"):
            self.assertEqual(TEMPLATE.count(f'id="footer-axis-{axis}"'), 1)
        self.assertIn('aria-label="Live axis positions"', TEMPLATE)
        self.assertIn('Number(getAxis(axis).position_mm)', APP_JS)
        self.assertIn('.footer-axis-positions', STYLE)
        self.assertIn('grid-template-areas: "positions time" "message message"', STYLE)

    def test_header_separates_motion_authority_from_machine_readiness(self) -> None:
        self.assertIn('id="strip-motion">DISABLED', TEMPLATE)
        self.assertIn('id="strip-readiness">INHIBITED', TEMPLATE)
        self.assertIn('MS.payload?.safety?.motion_enabled === true', APP_JS)
        self.assertIn('motionNode.textContent = motionEnabled ? "ENABLED" : "DISABLED"', APP_JS)
        self.assertIn('readinessNode.textContent = ready ? "READY" : "INHIBITED"', APP_JS)
        self.assertIn('id="strip-motion-reason" role="status" aria-atomic="true"', TEMPLATE)

    def test_header_uses_full_width_without_empty_logo_column(self) -> None:
        self.assertIn("Header v36: one full-width authority", STYLE)
        self.assertIn(".hmi-header .header-title { display:none !important; }", STYLE)
        self.assertIn("grid-template-columns:repeat(6,minmax(0,1fr)) !important", STYLE)
        self.assertIn("grid-template-columns:minmax(220px,265px) minmax(0,1fr) !important", STYLE)

    def test_motion_places_compact_home_left_and_jog_right(self) -> None:
        self.assertIn('primaryControls.className = "motion-primary-controls"', APP_JS)
        self.assertIn('primaryControls.append(homeZone)', APP_JS)
        self.assertIn('primaryControls.append(jogPanel)', APP_JS)
        self.assertIn('grid-template-columns: repeat(2, minmax(0, 1fr))', STYLE)
        self.assertIn('@media (max-width: 920px)', STYLE)

    def test_motion_v26_has_one_responsive_layout_authority(self) -> None:
        self.assertIn("Motion v26: one predictable responsive layout authority", STYLE)
        self.assertIn("grid-template-columns: minmax(360px, 0.78fr) minmax(560px, 1.22fr)", STYLE)
        self.assertIn("@media (max-width: 980px)", STYLE)
        self.assertIn("@media (max-width: 680px)", STYLE)

    def test_motion_has_one_visible_speed_control_bank(self) -> None:
        self.assertEqual(TEMPLATE.count('aria-label="Linked axis speed settings for jogging"'), 1)
        self.assertNotIn('Linked axis speed settings for minimum and maximum travel', TEMPLATE)
        self.assertNotIn('Linked axis speed settings for XYZ positioning', TEMPLATE)
        self.assertNotIn('jog-keyboard-help', TEMPLATE)
        self.assertNotIn('jog-hold-note', TEMPLATE)

    def test_hold_jog_uses_one_continuous_move_and_priority_release_stop(self) -> None:
        self.assertNotIn("HOLD_JOG_CHUNK_SECONDS", APP_JS)
        self.assertIn('apiCall("/api/motion/controlled-stop", "POST", {}, 2500)', APP_JS)
        self.assertIn('await apiCall("/api/jog", "POST", payload, 650000)', APP_JS)
        self.assertNotIn("while (MS.manualJog.active && MS.manualJog.token === token)", APP_JS)
        self.assertIn("if (continuous) body.continuous = true", APP_JS)
        self.assertIn("atDirectionalLimit", APP_JS)

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

    def test_target_positioning_has_one_speed_authority(self) -> None:
        for removed_id in (
            "target-speed", "target-duration", "move-timeout",
            "move-acceleration", "move-deceleration",
        ):
            self.assertNotIn(f'id="{removed_id}"', TEMPLATE)
        self.assertIn("body.speed_mm_s = effectiveMotionSpeed(participatingAxes)", APP_JS)
        self.assertNotIn('el("target-duration")', APP_JS)
        self.assertNotIn('el("move-timeout")', APP_JS)

    def test_advanced_diagnostics_are_read_only_and_use_live_state(self) -> None:
        self.assertNotIn('id="io-open-homing"', TEMPLATE)
        self.assertIn('id="architecture-health"', TEMPLATE)
        self.assertIn('id="sequence-order-title"', TEMPLATE)
        self.assertIn('architectureHealth.textContent = !MS.online', APP_JS)
        self.assertIn('setText("sequence-order-title"', APP_JS)

    def test_architecture_is_controller_centred_live_and_responsive(self) -> None:
        self.assertIn('class="architecture-map"', TEMPLATE)
        self.assertIn('id="architecture-controller-live"', TEMPLATE)
        self.assertIn("ONLY THIS PROCESS MAY AUTHORIZE MOTION", TEMPLATE)
        self.assertIn("STOP / DISARM / INHIBIT ALL FUTURE MOTION", TEMPLATE)
        self.assertIn('class="architecture-boundary-grid"', TEMPLATE)
        self.assertIn("setArchitectureLive", APP_JS)
        self.assertIn("Architecture v32: controller-centred topology", STYLE)
        self.assertIn("@media(max-width:820px)", STYLE)

    def test_home_controls_respect_explicit_motion_enable_latch(self) -> None:
        self.assertIn("MS.payload?.safety?.motion_enabled === false", APP_JS)
        self.assertIn("open System Control & Health and press ENABLE MOTION", APP_JS)
        self.assertIn('homeAllButton.setAttribute("aria-disabled"', APP_JS)

    def test_system_control_exposes_controller_owned_xy_drive_power_reset(self) -> None:
        self.assertIn('id="system-drive-power-reset"', TEMPLATE)
        self.assertIn('/api/system/drives/reset-power', APP_JS)
        self.assertIn('/api/system/drives/cut-power', APP_JS)
        self.assertIn('/api/system/drives/restore-power', APP_JS)
        self.assertIn('picontrol.outputs?.xy_drive_power', APP_JS)

    def test_io_status_separates_picontrol_from_iriv_modbus(self) -> None:
        self.assertIn('id="io-section-picontrol"', TEMPLATE)
        self.assertIn('id="io-page-picontrol-cards"', TEMPLATE)
        self.assertIn('data-io-filter="drive-alarms"', TEMPLATE)
        self.assertIn("MS.payload?.picontrol_io", APP_JS)
        self.assertIn("Separate local input bank; this is not IRIV Modbus", APP_JS)
        self.assertNotIn("📦", APP_JS)
        self.assertIn("<details", TEMPLATE)

    def test_diagnostics_expose_noise_homing_recovery_and_export(self) -> None:
        self.assertIn('id="io-summary-noise-count"', TEMPLATE)
        self.assertIn("detail.filtered_spikes", APP_JS)
        self.assertIn('class="io-diagnostic-meta"', APP_JS)
        self.assertIn("LATCH APPROACH", APP_JS)
        self.assertIn('class="home-seq-detail"', APP_JS)
        self.assertIn('class="alarm-recovery"', APP_JS)
        self.assertIn('id="system-action-history"', TEMPLATE)
        self.assertIn('id="event-export-csv"', TEMPLATE)
        self.assertIn("function exportFilteredEventsCsv()", APP_JS)
        self.assertIn("v31: authoritative diagnostics and recovery-detail layer", STYLE)

    def test_sequence_monitor_does_not_invent_a_workflow(self) -> None:
        self.assertIn("Array.isArray(operation.steps)", APP_JS)
        self.assertIn("if (!phaseOrder.length && phase) phaseOrder.push(phase)", APP_JS)
        self.assertNotIn('const phaseOrder = ["VALIDATE_SLOT"', APP_JS)


if __name__ == "__main__":
    unittest.main()
