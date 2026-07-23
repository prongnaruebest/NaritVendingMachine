import asyncio
import os
import unittest
from unittest.mock import MagicMock

from narit_vending.controller.server import IPCServer
from narit_vending.shared.commands import CommandEnvelope, CommandResult
from narit_vending.shared.snapshot import AxisSnapshot, MachineSnapshot
from narit_vending.web.ipc_client import ControllerClient


def _make_dummy_snapshot() -> MachineSnapshot:
    axes = {ax: AxisSnapshot(ax, 0.0, 0, True, False, False) for ax in ("x", "y", "z")}
    return MachineSnapshot(
        state="READY",
        estop=False,
        axes=axes,
        busy=False,
        active_command=None,
        command_id=None,
        command_started_at=None,
        command_estimated_duration_s=None,
        operation_phase="ready",
        operation_message="Ready",
        operation_axis=None,
        homing={"x": "passed", "y": "passed", "z": "passed"},
        last_error="",
        alarm_channels=[],
        config_revision="test_rev",
        motor_test_armed=False,
        configuration_restart_required=False,
        stop_requested=False,
        controlled_stop_requested=False,
        speed_override=None,
    )


import threading
import time


class TestIPCRoundTrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use TCP localhost for cross-platform unit testing
        os.environ["NARIT_CTRL_IPC"] = "tcp://127.0.0.1:7399"

        cls.bus = MagicMock()
        cls.bus.submit.return_value = CommandResult(
            accepted=True,
            command_id="cmd123",
            state="COMPLETED",
            result={"ok": True},
        )
        cls.snapshot_fn = _make_dummy_snapshot
        cls.config_fn = lambda: {"test_config": True}
        cls.save_config_fn = lambda cfg: {"saved": True}

        cls.server = IPCServer(cls.bus, cls.snapshot_fn, cls.config_fn, cls.save_config_fn)

        cls.loop = asyncio.new_event_loop()

        def _run_loop():
            asyncio.set_event_loop(cls.loop)
            cls.loop.run_until_complete(cls.server.start())
            cls.loop.run_forever()

        cls.thread = threading.Thread(target=_run_loop, daemon=True)
        cls.thread.start()
        time.sleep(0.2)  # Give server time to bind

    @classmethod
    def tearDownClass(cls):
        future = asyncio.run_coroutine_threadsafe(cls.server.stop(), cls.loop)
        future.result(timeout=2.0)
        cls.loop.call_soon_threadsafe(cls.loop.stop)
        cls.thread.join(timeout=2.0)

    def setUp(self):
        self.client = ControllerClient(
            timeout=1.0,
            addr={"transport": "tcp", "host": "127.0.0.1", "port": 7399, "path": ""},
        )

    def test_ping(self):
        self.assertTrue(self.client.ping())

    def test_snapshot(self):
        snap = self.client.snapshot()
        self.assertEqual(snap.state, "READY")
        self.assertEqual(snap.config_revision, "test_rev")

    def test_submit_command(self):
        env = CommandEnvelope(command_type="STOP", source="http", parameters={})
        res = self.client.submit_command(env)
        self.assertTrue(res.ok())
        self.assertEqual(res.command_id, "cmd123")

    def test_get_effective_config(self):
        cfg = self.client.get_effective_config()
        self.assertEqual(cfg.get("test_config"), True)


class TestWebIPCClientErrors(unittest.TestCase):
    def test_unreachable_controller_returns_false_on_ping(self):
        os.environ["NARIT_CTRL_IPC"] = "tcp://127.0.0.1:59999"  # invalid port
        client = ControllerClient(timeout=0.2)
        self.assertFalse(client.ping())

    def test_unreachable_controller_returns_offline_snapshot(self):
        os.environ["NARIT_CTRL_IPC"] = "tcp://127.0.0.1:59999"
        client = ControllerClient(timeout=0.2)
        snap = client.snapshot()
        self.assertEqual(snap.state, "CONTROLLER_OFFLINE")


if __name__ == "__main__":
    unittest.main()
