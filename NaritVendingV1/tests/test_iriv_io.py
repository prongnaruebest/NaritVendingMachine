from __future__ import annotations

import time
import unittest

from narit_vending.iriv_io import IRIVIOBackend, IRIVIOError


class FakeModbusClient:
    def __init__(self) -> None:
        self.inputs = [False] * 11
        self.writes: list[tuple[int, bool]] = []
        self.error: Exception | None = None

    def read_discrete_inputs(self, start: int, count: int) -> list[bool]:
        if self.error:
            raise self.error
        return self.inputs[start:start + count]

    def write_single_coil(self, address: int, value: bool) -> None:
        if self.error:
            raise self.error
        self.writes.append((address, value))

    def close(self) -> None:
        return None


def _config() -> dict:
    names = ["estop", "x_head_limit", "x_tail_limit", "y_head_limit", "y_tail_limit",
             "z_head_limit", "z_tail_limit", "x_alarm", "y_alarm", "z_alarm", "door"]
    inputs = {
        name: {
            "channel": channel,
            "active_state": False if name in {"estop", "door"} else True,
            "fail_safe": name in {"estop", "door", "x_alarm", "y_alarm", "z_alarm"},
        }
        for channel, name in enumerate(names)
    }
    outputs = {name: {"channel": channel, "active_high": True} for channel, name in enumerate(("ready", "moving", "alarm", "dispense"))}
    return {"host": "10.0.0.10", "port": 502, "unit_id": 255, "poll_interval_s": 0.02,
            "stale_after_s": 0.04, "inputs": inputs, "outputs": outputs, "dispense": {"pulse_ms": 20}}


class IRIVIOBackendTests(unittest.TestCase):
    def test_maps_di_and_coils(self) -> None:
        client = FakeModbusClient()
        client.inputs[0] = True   # E-stop safety feedback healthy
        client.inputs[1] = True   # X head limit active
        client.inputs[10] = True  # Door safety feedback healthy
        backend = IRIVIOBackend(_config(), client=client)
        backend.start()
        try:
            self.assertTrue(backend.communication_ok)
            self.assertFalse(backend.input_active("estop"))
            self.assertTrue(backend.input_active("x_head_limit"))
            self.assertFalse(backend.input_active("door"))
            backend.set_output("dispense", True)
            self.assertIn((0x0103, True), client.writes)
        finally:
            backend.close()

    def test_communication_loss_is_immediately_fail_safe(self) -> None:
        client = FakeModbusClient()
        client.inputs[0] = True
        client.inputs[10] = True
        backend = IRIVIOBackend(_config(), client=client)
        backend.start()
        try:
            self.assertFalse(backend.input_active("estop"))
            client.error = IRIVIOError("link down")
            backend._poll_once()
            self.assertFalse(backend.communication_ok)
            self.assertTrue(backend.input_active("estop"))
            self.assertTrue(backend.input_active("door"))
            with self.assertRaises(IRIVIOError):
                backend.set_output("ready", True)
        finally:
            backend.close()

    def test_stale_data_becomes_not_ready_without_waiting_for_next_poll(self) -> None:
        client = FakeModbusClient()
        client.inputs[0] = True
        client.inputs[10] = True
        backend = IRIVIOBackend(_config(), client=client)
        backend._poll_once()
        self.assertTrue(backend.communication_ok)
        time.sleep(0.05)
        self.assertFalse(backend.communication_ok)
        self.assertTrue(backend.input_active("estop"))

    def test_unverified_safety_polarity_remains_fail_safe_active(self) -> None:
        client = FakeModbusClient()
        config = _config()
        config["inputs"]["estop"]["polarity_verified"] = False
        client.inputs[0] = True
        backend = IRIVIOBackend(config, client=client)
        backend._poll_once()
        self.assertTrue(backend.communication_ok)
        self.assertTrue(backend.input_active("estop"))


if __name__ == "__main__":
    unittest.main()
