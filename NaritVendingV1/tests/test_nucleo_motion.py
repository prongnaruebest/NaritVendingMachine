"""Unit tests for Nucleo Protocol v2 motion and pulse generation."""

from __future__ import annotations

import json
import unittest

from narit_vending.nucleo import (
    NUCLEO_MOTION_MAX_SPEED_HZ,
    NUCLEO_MOTION_MAX_STEPS,
    NUCLEO_MOTION_MIN_SPEED_HZ,
    NucleoError,
    NucleoLink,
)


class MockSerialProtocolV2:
    def __init__(self, script: list[dict | str] | None = None) -> None:
        self.script = list(script or [])
        self.writes: list[bytes] = []
        self.closed = False

    def write(self, data: bytes) -> int:
        self.writes.append(data)
        line = data.decode("ascii", errors="replace").strip()
        if line == "ARM SAFE":
            self.script.append({"type": "ack", "status": "armed"})
        elif line == "DISARM" or line == "STOP":
            self.script.append({"type": "ack", "status": "disarmed"})
        elif line.startswith("MOVE "):
            self.script.append({"type": "ack", "status": "moving"})
            self.script.append({
                "type": "heartbeat",
                "device": "NUCLEO-F439ZI",
                "protocol": 2,
                "safe": False,
                "armed": True,
                "watchdog": True,
                "moving": {"x": 0, "y": 0, "z": 0},
            })
        elif line == "PING" or line == "STATUS":
            self.script.append({
                "type": "pong",
                "device": "NUCLEO-F439ZI",
                "protocol": 2,
                "safe": True,
                "armed": False,
                "watchdog": False,
                "uptime_ms": 1000,
                "moving": {"x": 0, "y": 0, "z": 0},
            })
        elif line == "HEARTBEAT SAFE":
            self.script.append({
                "type": "heartbeat",
                "device": "NUCLEO-F439ZI",
                "protocol": 2,
                "safe": False,
                "armed": True,
                "watchdog": True,
                "uptime_ms": 1010,
                "moving": {"x": 0, "y": 0, "z": 0},
            })
        return len(data)

    def flush(self) -> None:
        pass

    def reset_input_buffer(self) -> None:
        pass

    def readline(self) -> bytes:
        if not self.script:
            return b""
        item = self.script.pop(0)
        if isinstance(item, dict):
            return json.dumps(item).encode("ascii") + b"\r\n"
        return str(item).encode("ascii") + b"\r\n"

    def close(self) -> None:
        self.closed = True


class NucleoMotionTests(unittest.TestCase):
    def config(self) -> dict:
        return {
            "port": "test_port",
            "baudrate": 115200,
            "timeout_s": 0.1,
            "poll_interval_s": 0.1,
            "stale_after_s": 0.5,
            "expected_device": "NUCLEO-F439ZI",
            "protocol_version": 2,
        }

    def test_protocol_v2_ping_and_status(self):
        mock_serial = MockSerialProtocolV2()
        link = NucleoLink(self.config(), serial_factory=lambda **kwargs: mock_serial)
        link._poll_once()

        self.assertTrue(link.communication_ok)
        payload = link.status_payload()
        self.assertEqual(payload["protocol"], 2)
        self.assertEqual(payload["device"], "NUCLEO-F439ZI")
        self.assertFalse(payload["armed"])

    def test_arm_and_disarm(self):
        mock_serial = MockSerialProtocolV2()
        link = NucleoLink(self.config(), serial_factory=lambda **kwargs: mock_serial)
        link._poll_once()

        self.assertTrue(link.arm(safety_permissive=True))
        self.assertTrue(link.is_armed)

        self.assertTrue(link.disarm())
        self.assertFalse(link.is_armed)

    def test_move_validates_parameters(self):
        mock_serial = MockSerialProtocolV2()
        link = NucleoLink(self.config(), serial_factory=lambda **kwargs: mock_serial)
        link._poll_once()

        with self.assertRaises(NucleoError):
            link.move("W", 0, 100, 200)

        with self.assertRaises(NucleoError):
            link.move("X", 0, 0, 200)
        with self.assertRaises(NucleoError):
            link.move("X", 0, NUCLEO_MOTION_MAX_STEPS + 1, 200)

        with self.assertRaises(NucleoError):
            link.move("X", 0, 100, NUCLEO_MOTION_MIN_SPEED_HZ - 1)
        with self.assertRaises(NucleoError):
            link.move("X", 0, 100, NUCLEO_MOTION_MAX_SPEED_HZ + 1)

    def test_move_executes_and_completes(self):
        mock_serial = MockSerialProtocolV2()
        link = NucleoLink(self.config(), serial_factory=lambda **kwargs: mock_serial)
        link._poll_once()

        result = link.move("X", 1, 200, 400)
        self.assertTrue(result["ok"])
        self.assertEqual(result["axis"], "x")
        self.assertEqual(result["direction"], 1)
        self.assertEqual(result["steps"], 200)
        self.assertEqual(result["speed_hz"], 400.0)

        commands = [w.decode("ascii", errors="replace").strip() for w in mock_serial.writes]
        self.assertIn("ARM SAFE", commands)
        self.assertIn("MOVE X 1 200 400", commands)

    def test_move_stops_when_condition_triggers(self):
        mock_serial = MockSerialProtocolV2()
        link = NucleoLink(self.config(), serial_factory=lambda **kwargs: mock_serial)
        link._poll_once()

        with self.assertRaises(NucleoError) as ctx:
            link.move("Y", 0, 500, 200, stop_requested=lambda: True)

        self.assertIn("aborted", str(ctx.exception).lower())
        commands = [w.decode("ascii", errors="replace").strip() for w in mock_serial.writes]
        self.assertIn("STOP", commands)


if __name__ == "__main__":
    unittest.main()
