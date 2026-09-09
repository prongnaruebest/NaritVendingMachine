import argparse
import tempfile
from pathlib import Path

import pytest

from narit_vending.controller.__main__ import _build_command_bus
from narit_vending.controller.state_machine import MachineState, StateMachine
from narit_vending.shared.commands import CommandEnvelope, CommandResult
from narit_vending.shared.snapshot import AxisSnapshot, MachineSnapshot


def snapshot() -> MachineSnapshot:
    return MachineSnapshot(
        state="READY",
        estop=False,
        axes={axis: AxisSnapshot(axis, 0.0, 0, True, False, False) for axis in ("x", "y", "z")},
        busy=False,
        active_command=None,
        command_id=None,
        command_started_at=None,
        command_estimated_duration_s=None,
        operation_phase="ready",
        operation_message="Ready",
        operation_axis=None,
        homing={"x": "complete", "y": "complete", "z": "complete"},
        last_error="",
        alarm_channels=[],
        config_revision="rev-test",
        motor_test_armed=False,
        configuration_restart_required=False,
        stop_requested=False,
        controlled_stop_requested=False,
        speed_override=None,
    )


def args(config: Path, persistence_db: Path | None = None) -> argparse.Namespace:
    return argparse.Namespace(config=str(config), persistence_db=str(persistence_db) if persistence_db else None)


def test_runtime_bus_uses_database_beside_machine_config_by_default() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        bus = _build_command_bus(StateMachine(MachineState.READY), snapshot, args(root / "machine.json"))

        assert bus._audit.database_path.resolve() == root.resolve() / "controller_history.sqlite3"
        assert bus._idempotency.database_path.resolve() == root.resolve() / "controller_history.sqlite3"


def test_runtime_bus_rejects_demo_database_as_command_history() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        namespace = args(root / "machine.json", root / "demo_results.sqlite3")

        with pytest.raises(ValueError, match="must differ"):
            _build_command_bus(StateMachine(MachineState.READY), snapshot, namespace)


def test_runtime_bus_persists_audit_and_prevents_reexecution_after_restart() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "history.sqlite3"
        namespace = args(Path(directory) / "machine.json", database)
        calls = 0

        def handler(envelope: CommandEnvelope) -> CommandResult:
            nonlocal calls
            calls += 1
            return CommandResult(True, envelope.command_id, "COMPLETED")

        envelope = CommandEnvelope(
            command_type="JOG",
            source="test",
            parameters={"axis": "x", "distance_mm": 1.0},
            idempotency_key="restart-safe",
        )
        first = _build_command_bus(StateMachine(MachineState.READY), snapshot, namespace)
        first.register("JOG", handler)
        assert first.submit(envelope).ok()

        restarted = _build_command_bus(StateMachine(MachineState.READY), snapshot, namespace)
        restarted.register("JOG", handler)
        assert restarted.submit(envelope).ok()

        events = restarted.recent_audit_events()
        assert calls == 1
        assert [event.event_code for event in events[:2]] == ["COMMAND_REPLAYED", "COMMAND_COMPLETED"]
        assert all(event.command_id == envelope.command_id for event in events[:2])
