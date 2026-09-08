from types import SimpleNamespace
from unittest.mock import MagicMock

from narit_vending.controller.handlers.settings import make_set_speed_handler, make_set_timer_handler
from narit_vending.shared.commands import CommandEnvelope


def envelope(command_type: str, parameters: dict) -> CommandEnvelope:
    return CommandEnvelope(command_type=command_type, source="http", parameters=parameters)  # type: ignore[arg-type]


def test_speed_setting_is_owned_by_controller_service() -> None:
    service = SimpleNamespace(set_speed=MagicMock(return_value={"ok": True, "speed_mm_s": 12.5}))
    result = make_set_speed_handler(service)(envelope("SET_SPEED", {"speed_mm_s": 12.5}))
    assert result.ok()
    service.set_speed.assert_called_once_with(12.5)


def test_timer_setting_is_owned_by_controller_service() -> None:
    service = SimpleNamespace(set_timer=MagicMock(return_value={"ok": True, "timer_seconds": 7.0}))
    result = make_set_timer_handler(service)(envelope("SET_TIMER", {"duration_s": 7}))
    assert result.ok()
    service.set_timer.assert_called_once_with(7.0)


def test_invalid_settings_are_rejected_before_service_call() -> None:
    service = SimpleNamespace(set_speed=MagicMock(), set_timer=MagicMock())
    assert not make_set_speed_handler(service)(envelope("SET_SPEED", {"speed_mm_s": "bad"})).ok()
    assert not make_set_timer_handler(service)(envelope("SET_TIMER", {})).ok()
    service.set_speed.assert_not_called()
    service.set_timer.assert_not_called()
