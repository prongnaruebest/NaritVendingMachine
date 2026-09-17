from __future__ import annotations

from types import SimpleNamespace
import unittest

from narit_vending.domain.motion_profile_routing import ProfileOperation, decide_profile_route


def config(axis: str, enabled: bool | None):
    return SimpleNamespace(name=axis, scurve_enabled=enabled)


class TestMotionProfileRouting(unittest.TestCase):
    def test_disabled_xy_uses_existing_route(self):
        for operation in ProfileOperation:
            decision = decide_profile_route(config("x", False), operation, capability_ready=False, runtime_ready=False)
            self.assertTrue(decision.executable)
            self.assertEqual(decision.route, "legacy")

    def test_z_always_remains_on_existing_route(self):
        for operation in ProfileOperation:
            decision = decide_profile_route(config("z", None), operation, capability_ready=True, runtime_ready=True)
            self.assertTrue(decision.executable)
            self.assertEqual(decision.route, "legacy")

    def test_enabled_xy_fails_closed_when_capability_disappears(self):
        decision = decide_profile_route(config("y", True), ProfileOperation.MOVE, capability_ready=False, runtime_ready=True)
        self.assertFalse(decision.executable)
        self.assertEqual(decision.route, "blocked")
        self.assertIn("handshake", decision.reason)

    def test_host_supervised_homing_uses_legacy_motion_path(self):
        for operation in (ProfileOperation.HOME, ProfileOperation.LIMIT_SEEK):
            decision = decide_profile_route(config("x", True), operation, capability_ready=True, runtime_ready=True)
            self.assertTrue(decision.executable)
            self.assertEqual(decision.route, "legacy")
            self.assertIn("host-supervised", decision.reason.lower())

    def test_sensor_terminated_operations_are_not_misrouted_to_bounded_profile(self):
        for operation in (ProfileOperation.HOME, ProfileOperation.LIMIT_SEEK):
            decision = decide_profile_route(
                config("x", True), operation,
                capability_ready=True, runtime_ready=True, allow_host_supervised_homing=False,
            )
            self.assertFalse(decision.executable)
            self.assertIn("sensor-terminated", decision.reason.lower())

    def test_sensor_terminated_operations_route_only_after_all_gates(self):
        for operation in (ProfileOperation.HOME, ProfileOperation.LIMIT_SEEK):
            decision = decide_profile_route(
                config("x", True), operation,
                capability_ready=True, runtime_ready=True, sensor_termination_ready=True,
            )
            self.assertTrue(decision.executable)
            self.assertEqual(decision.route, "sensor_terminated_scurve")

    def test_bounded_xy_profile_requires_connected_runtime(self):
        for operation in (ProfileOperation.MOVE, ProfileOperation.JOG):
            disconnected = decide_profile_route(config("x", True), operation, capability_ready=True, runtime_ready=False)
            connected = decide_profile_route(config("x", True), operation, capability_ready=True, runtime_ready=True)
            self.assertFalse(disconnected.executable)
            self.assertTrue(connected.executable)
            self.assertEqual(connected.route, "buffered_scurve")


if __name__ == "__main__":
    unittest.main()
