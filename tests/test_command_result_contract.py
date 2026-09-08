import pytest

from narit_vending.shared.commands import CommandEnvelope, CommandMetadata, CommandResult


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


def test_command_metadata_survives_round_trip() -> None:
    envelope = CommandEnvelope(
        command_type="STOP",
        source="http",
        parameters={},
        metadata=CommandMetadata(
            correlation_id="session-17",
            actor="operator-panel",
            client_revision="ui-v35",
        ),
    )

    restored = CommandEnvelope.from_dict(envelope.to_dict())

    assert restored.metadata == envelope.metadata
    assert restored.metadata.schema_version == 1


def test_legacy_command_without_metadata_is_still_accepted() -> None:
    restored = CommandEnvelope.from_dict(
        {"command_type": "STOP", "source": "http", "parameters": {}}
    )

    assert restored.metadata == CommandMetadata()


def test_unknown_metadata_schema_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported command metadata"):
        CommandEnvelope.from_dict(
            {
                "command_type": "STOP",
                "source": "http",
                "parameters": {},
                "metadata": {"schema_version": 99},
            }
        )
