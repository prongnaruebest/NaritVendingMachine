import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from narit_vending.controller.homing_orchestrator import HomingOrchestrator


def make_axis(name, *, protocol=2, home_position=0.0, backend=None):
    axis = MagicMock()
    axis.config = SimpleNamespace(
        name=name,
        home_direction=0,
        max_pulse_hz=50_000.0,
        homing_search_speed_mm_s=20.0,
        steps_per_mm=80.0,
        homing_timeout_s=120.0,
        home_position_mm=home_position,
        commissioned_max_speed_mm_s=5.0,
    )
    axis.motion_backend = backend or SimpleNamespace(expected_protocol=protocol)
    axis.head_limit = SimpleNamespace(value=False)
    axis.estop = SimpleNamespace(value=False)
    axis.stop_requested.return_value = False
    axis.is_homed = True
    return axis


class HomingOrchestratorTests(unittest.TestCase):
    def test_protocol_v2_uses_configured_sequential_order(self):
        axes = {name: make_axis(name) for name in ("x", "y", "z")}
        order = []
        for name, axis in axes.items():
            axis.home.side_effect = lambda progress=None, current=name: order.append(current)
        orchestrator = HomingOrchestrator(axes=lambda: axes, home_order=("z", "y", "x"))

        orchestrator.home_all()

        self.assertEqual(order, ["z", "y", "x"])

    def test_home_offset_failure_clears_homed_state(self):
        axis = make_axis("x", home_position=10.0)
        axis.move_to_mm.side_effect = RuntimeError("offset failed")
        orchestrator = HomingOrchestrator(axes=lambda: {"x": axis}, home_order=("x",))

        with self.assertRaisesRegex(RuntimeError, "offset failed"):
            orchestrator.home_axis("x")

        self.assertFalse(axis.is_homed)

    def test_protocol_v3_capability_invokes_parallel_search(self):
        backend = MagicMock(expected_protocol=3)
        axes = {name: make_axis(name, backend=backend) for name in ("x", "y", "z")}
        orchestrator = HomingOrchestrator(axes=lambda: axes, home_order=("z", "y", "x"))

        orchestrator.home_all()

        backend.home_parallel.assert_called_once()
        plans = backend.home_parallel.call_args.args[0]
        self.assertEqual(set(plans), {"x", "y", "z"})
        self.assertEqual(plans["x"]["speed_hz"], 1_600.0)

    def test_progress_contract_is_preserved(self):
        axis = make_axis("z", home_position=5.0)
        axis.home.side_effect = lambda progress=None: progress("completed")
        events = []
        orchestrator = HomingOrchestrator(axes=lambda: {"z": axis}, home_order=("z",))

        orchestrator.home_axis("z", progress=lambda name, phase: events.append((name, phase)))

        self.assertEqual(events, [("z", "completed"), ("z", "positioning"), ("z", "passed")])


if __name__ == "__main__":
    unittest.main()
