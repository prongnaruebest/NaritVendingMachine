from unittest.mock import patch

from narit_vending.controller.clock import SystemClock
from narit_vending.controller.ports import ClockPort, IRIVIOPort, NucleoTransportPort, PiControlIOPort
from narit_vending.iriv_io import IRIVIOBackend
from narit_vending.nucleo import NucleoLink
from narit_vending.picontrol_io import PiControlIOBackend

class FakeModbusClient:
    def read_discrete_inputs(self, start: int, count: int) -> list[bool]:
        return [False] * count

    def write_single_coil(self, address: int, value: bool) -> None:
        return None

    def close(self) -> None:
        return None


class FakeInput:
    def __init__(self, pin: int, pull_up: bool = False) -> None:
        self.pin = pin

    @property
    def value(self) -> bool:
        return False

    def close(self) -> None:
        return None


def iriv_config() -> dict:
    return {
        "inputs": {"estop": {"channel": 0, "active_state": True, "fail_safe": True}},
        "outputs": {},
    }


def picontrol_config() -> dict:
    return {
        "inputs": {"x_alarm": {"channel": 0, "pin": 13, "active_state": True}},
        "outputs": {},
    }


def test_system_clock_conforms_to_clock_port() -> None:
    assert isinstance(SystemClock(), ClockPort)


def test_nucleo_adapter_conforms_without_opening_usb() -> None:
    link = NucleoLink(
        {
            "port": "contract-only",
            "baudrate": 115200,
            "timeout_s": 0.1,
            "poll_interval_s": 0.1,
            "stale_after_s": 0.5,
            "expected_device": "NUCLEO-F439ZI",
            "protocol_version": 2,
        }
    )
    assert isinstance(link, NucleoTransportPort)


def test_iriv_adapter_conforms_without_network() -> None:
    backend = IRIVIOBackend(iriv_config(), client=FakeModbusClient())
    assert isinstance(backend, IRIVIOPort)


@patch("narit_vending.picontrol_io.DigitalInputDevice", FakeInput)
def test_picontrol_adapter_conforms_with_fake_gpio() -> None:
    backend = PiControlIOBackend(picontrol_config())
    assert isinstance(backend, PiControlIOPort)
    backend.close()
