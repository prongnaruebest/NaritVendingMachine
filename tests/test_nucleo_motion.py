"""Unit tests for Nucleo Protocol v2 motion and pulse generation."""

from __future__ import annotations

import json
import unittest

from narit_vending.nucleo import (
    NUCLEO_MOTION_MAX_SPEED_HZ,
    NUCLEO_MOTION_MAX_STEPS,
    NUCLEO_LEGACY_MAX_STEPS,
    NUCLEO_MOTION_MIN_SPEED_HZ,
    NUCLEO_SERIAL_READ_SLICE_S,
    NucleoError,
    NucleoLink,
)
from narit_vending.domain.nucleo_profile_protocol import DynamicStartCommand


class MockSerialProtocolV2:
    def __init__(self, script: list[dict | str] | None = None, protocol: int = 2) -> None:
        self.script = list(script or [])
        self.protocol = protocol
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
                "protocol": self.protocol,
                "safe": False,
                "armed": True,
                "watchdog": True,
                "moving": {"x": 0, "y": 0, "z": 0},
            })
        elif line == "PING" or line == "STATUS":
            self.script.append({
                "type": "pong",
                "device": "NUCLEO-F439ZI",
                "protocol": self.protocol,
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
                "protocol": self.protocol,
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
        self.script.clear()

    def readline(self) -> bytes:
        if not self.script:
            return b""
        item = self.script.pop(0)
        if isinstance(item, dict):
            return json.dumps(item).encode("ascii") + b"\r\n"
        return str(item).encode("ascii") + b"\r\n"

    def close(self) -> None:
        self.closed = True


class MockDynamicSerial(MockSerialProtocolV2):
    """Protocol-v4 fake reproducing the post-DYN_START moving-bit race."""

    def __init__(self) -> None:
        super().__init__(protocol=4)
        self.dynamic_status_count = 0
        self.dynamic_heartbeat_count = 0

    def write(self, data: bytes) -> int:
        line = data.decode("ascii", errors="replace").strip()
        if line.startswith("DYN_START "):
            self.writes.append(data)
            self.script.append({"type": "ack", "status": "running"})
            return len(data)
        if line == "HEARTBEAT SAFE":
            self.writes.append(data)
            self.dynamic_heartbeat_count += 1
            self.script.append({
                "type": "heartbeat",
                "device": "NUCLEO-F439ZI",
                "protocol": 4,
                "safe": False,
                "armed": True,
                "watchdog": True,
                # The deployed firmware can transiently report zero while the
                # dynamic status remains RUNNING. Completion must not be
                # inferred from this field alone.
                "moving": {"x": 0, "y": 0, "z": 0},
            })
            return len(data)
        if line == "DYN_STATUS":
            self.writes.append(data)
            self.dynamic_status_count += 1
            complete = self.dynamic_status_count >= 2
            self.script.append({
                "type": "dynamic_status",
                "runtime_ready": True,
                "axes": {
                    "x": {
                        "state": "COMPLETE" if complete else "RUNNING",
                        "fault": "NONE",
                        "emitted_pulses": 100 if complete else 16,
                        "remaining_pulses": 0 if complete else 84,
                    },
                    "y": {
                        "state": "IDLE",
                        "fault": "NONE",
                        "emitted_pulses": 0,
                        "remaining_pulses": 0,
                    },
                },
            })
            return len(data)
        return super().write(data)


class MockStalledDynamicSerial(MockDynamicSerial):
    """Dynamic fake that preserves terminal telemetry until host timeout."""

    def write(self, data: bytes) -> int:
        line = data.decode("ascii", errors="replace").strip()
        if line == "DYN_STATUS":
            self.writes.append(data)
            self.dynamic_status_count += 1
            self.script.append({
                "type": "dynamic_status",
                "runtime_ready": True,
                "axes": {
                    "x": {
                        "state": "RUNNING",
                        "fault": "NONE",
                        "emitted_pulses": 99,
                        "remaining_pulses": 1,
                        "output_rate_millihz": 2500,
                    },
                    "y": {"state": "IDLE", "fault": "NONE"},
                },
            })
            return len(data)
        return super().write(data)


class MockControlledStopDynamicSerial(MockDynamicSerial):
    """Protocol-v4 fake returns a confirmed coordinate after smooth stop."""

    def write(self, data: bytes) -> int:
        line = data.decode("ascii", errors="replace").strip()
        if line == "CONTROLLED_STOP":
            self.writes.append(data)
            self.script.append({"type": "ack", "status": "stopping"})
            return len(data)
        if line == "DYN_STATUS":
            self.writes.append(data)
            self.dynamic_status_count += 1
            self.script.append({
                "type": "dynamic_status",
                "runtime_ready": True,
                "axes": {
                    "x": {
                        "position_valid": True,
                        "position_pulses": 321,
                        "state": "IDLE",
                        "fault": "NONE",
                        "emitted_pulses": 321,
                        "remaining_pulses": 679,
                    },
                    "y": {"state": "IDLE", "fault": "NONE"},
                },
            })
            return len(data)
        return super().write(data)


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
        self.assertEqual(payload["max_move_steps"], NUCLEO_LEGACY_MAX_STEPS)
        self.assertFalse(payload["armed"])

    def test_serial_read_timeout_is_bounded_below_firmware_watchdog(self):
        captured: dict[str, object] = {}
        mock_serial = MockSerialProtocolV2()

        def factory(**kwargs):
            captured.update(kwargs)
            return mock_serial

        config = self.config()
        config["timeout_s"] = 1.0
        link = NucleoLink(config, serial_factory=factory)
        link._open_serial()

        self.assertEqual(captured["timeout"], NUCLEO_SERIAL_READ_SLICE_S)
        self.assertLess(float(captured["timeout"]), 0.5)

    def test_usb_open_failure_publishes_communication_fault(self):
        def fail_serial(**kwargs):
            raise OSError("USB device unavailable")

        link = NucleoLink(self.config(), serial_factory=fail_serial)
        link._poll_once()

        self.assertFalse(link.communication_ok)
        self.assertTrue(link.alarm_channel()["active"])
        self.assertIn("USB device unavailable", link.status_payload()["last_error"])

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
            link.move("X", 0, NUCLEO_LEGACY_MAX_STEPS + 1, 200)

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
        self.assertIn("DISARM", commands)
        self.assertFalse(link.is_armed)

        # The last wire heartbeat was captured while armed; the acknowledged
        # DISARM must replace those stale safety fields immediately.
        status = link.status_payload()
        self.assertTrue(status["safe"])
        self.assertFalse(status["armed"])
        self.assertFalse(status["watchdog"])
        self.assertEqual(status["moving"], {"x": 0, "y": 0, "z": 0})

    def test_disarm_fails_closed_without_acknowledgement(self):
        mock_serial = MockSerialProtocolV2()
        link = NucleoLink(self.config(), serial_factory=lambda **kwargs: mock_serial)
        link._poll_once()
        self.assertTrue(link.arm(safety_permissive=True))

        original_write = mock_serial.write

        def drop_disarm_ack(data: bytes) -> int:
            if data.decode("ascii", errors="replace").strip() == "DISARM":
                mock_serial.writes.append(data)
                return len(data)
            return original_write(data)

        mock_serial.write = drop_disarm_ack  # type: ignore[method-assign]

        self.assertFalse(link.disarm())
        self.assertIn("not acknowledged", link.status_payload()["last_error"])

    def test_dynamic_completion_keeps_heartbeat_channel_lean_then_verifies_status(self):
        mock_serial = MockDynamicSerial()
        config = self.config()
        config.update({"protocol_version": 4, "expected_device": "NUCLEO-F439ZI"})
        link = NucleoLink(config, serial_factory=lambda **kwargs: mock_serial)
        link._connected = True
        link._last_success_monotonic = __import__("time").monotonic()

        result = link.start_dynamic_motion(
            DynamicStartCommand(command_id="move-1", axes=("x",)),
            timeout_s=3.0,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(mock_serial.dynamic_status_count, 2)
        heartbeat_count = sum(
            write.decode("ascii", errors="replace").strip() == "HEARTBEAT SAFE"
            for write in mock_serial.writes
        )
        self.assertGreater(heartbeat_count, mock_serial.dynamic_status_count)
        self.assertEqual(result["telemetry"]["axes"]["x"]["state"], "COMPLETE")
        self.assertEqual(result["telemetry"]["axes"]["x"]["remaining_pulses"], 0)

    def test_dynamic_timeout_reports_last_terminal_telemetry(self):
        mock_serial = MockStalledDynamicSerial()
        config = self.config()
        config.update({"protocol_version": 4, "expected_device": "NUCLEO-F439ZI"})
        link = NucleoLink(config, serial_factory=lambda **kwargs: mock_serial)
        link._connected = True
        link._last_success_monotonic = __import__("time").monotonic()

        with self.assertRaisesRegex(
            NucleoError,
            r"last_status=X\(state=RUNNING,fault=NONE,emitted=99,remaining=1,rate_millihz=2500\)",
        ):
            link.start_dynamic_motion(
                DynamicStartCommand(command_id="move-stalled", axes=("x",)),
                timeout_s=1.0,
            )

    def test_dynamic_controlled_stop_returns_terminal_position_telemetry(self):
        mock_serial = MockControlledStopDynamicSerial()
        config = self.config()
        config.update({"protocol_version": 4, "expected_device": "NUCLEO-F439ZI"})
        link = NucleoLink(config, serial_factory=lambda **kwargs: mock_serial)
        link._connected = True
        link._last_success_monotonic = __import__("time").monotonic()

        result = link.start_dynamic_motion(
            DynamicStartCommand(command_id="jog-release", axes=("x",)),
            timeout_s=3.0,
            stop_requested=lambda: True,
        )

        self.assertTrue(result["stopped"])
        self.assertEqual(result["telemetry"]["axes"]["x"]["position_pulses"], 321)
        commands = [item.decode("ascii", errors="replace").strip() for item in mock_serial.writes]
        self.assertIn("CONTROLLED_STOP", commands)
        self.assertIn("DYN_STATUS", commands)

    def test_move_stops_when_condition_triggers(self):
        mock_serial = MockSerialProtocolV2()
        link = NucleoLink(self.config(), serial_factory=lambda **kwargs: mock_serial)
        link._poll_once()

        result = link.move("Y", 0, 500, 200, stop_requested=lambda: True)

        self.assertTrue(result["ok"])
        self.assertTrue(result["stopped"])
        self.assertLessEqual(result["steps"], 500)
        commands = [w.decode("ascii", errors="replace").strip() for w in mock_serial.writes]
        self.assertIn("STOP", commands)

    def test_protocol_v3_parallel_move_starts_every_axis_on_nucleo(self):
        mock_serial = MockSerialProtocolV2(protocol=3)
        config = self.config()
        config["protocol_version"] = 3
        link = NucleoLink(config, serial_factory=lambda **kwargs: mock_serial)
        link._poll_once()

        result = link.move_parallel(
            {
                "x": {"direction": 0, "steps": 200, "speed_hz": 400},
                "y": {"direction": 1, "steps": 100, "speed_hz": 200},
            },
            timeout_s=2.0,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["steps"], {"x": 200, "y": 100})
        commands = [w.decode("ascii", errors="replace").strip() for w in mock_serial.writes]
        self.assertIn("MOVE X 0 200 400", commands)
        self.assertIn("MOVE Y 1 100 200", commands)
        self.assertIn("HEARTBEAT SAFE", commands)
        self.assertIn("DISARM", commands)

    def test_nucleo_error_is_motion_error(self):
        from narit_vending.motion import MotionError
        self.assertTrue(issubclass(NucleoError, MotionError))

    def test_serial_sync_ignores_stale_boot_and_pong_during_arm_and_move(self):
        mock_serial = MockSerialProtocolV2([
            {"type": "boot", "device": "NUCLEO-F439ZI", "protocol": 2, "safe": True, "armed": False},
            {"type": "pong", "device": "NUCLEO-F439ZI", "protocol": 2, "safe": True, "armed": False, "watchdog": False, "uptime_ms": 100},
        ])
        link = NucleoLink(self.config(), serial_factory=lambda **kwargs: mock_serial)
        link._poll_once()
        self.assertTrue(link.communication_ok)

        mock_serial.script.append({
            "type": "pong",
            "device": "NUCLEO-F439ZI",
            "protocol": 2,
            "safe": True,
            "armed": False,
            "watchdog": False,
            "uptime_ms": 200,
        })
        self.assertTrue(link.arm(safety_permissive=True))
        self.assertTrue(link.is_armed)

    def test_homing_uses_negotiated_continuous_move_window(self):
        motion_source = (
            __import__("pathlib").Path(__file__).resolve().parents[1]
            / "narit_vending"
            / "motion.py"
        ).read_text(encoding="utf-8")

        self.assertIn("search_frame_steps = min(", motion_source)
        self.assertIn('getattr(self.motion_backend, "max_move_steps"', motion_source)
        self.assertNotIn("chunk_steps = 10_000", motion_source)


if __name__ == "__main__":
    unittest.main()
