from narit_vending.shared.commands import CommandResult


def test_rejection_keeps_legacy_fields_and_adds_structured_error() -> None:
    payload = CommandResult.rejected(
        "cmd-1",
        "Emergency stop is active",
        code="SAFETY_INTERLOCK",
    ).to_dict()

    assert payload["ok"] is False
    assert payload["accepted"] is False
    assert payload["state"] == "REJECTED"
    assert payload["reason"] == "Emergency stop is active"
    assert payload["error"] == {
        "code": "SAFETY_INTERLOCK",
        "message": "Emergency stop is active",
        "details": {},
        "retryable": False,
    }


def test_structured_error_survives_ipc_round_trip() -> None:
    original = CommandResult.busy("cmd-2")
    restored = CommandResult.from_dict(original.to_dict())

    assert restored.reason == original.reason
    assert restored.error == original.error
    assert restored.error is not None
    assert restored.error["code"] == "MACHINE_BUSY"
    assert restored.error["retryable"] is True
