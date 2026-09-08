import threading

from narit_vending.controller.command_bus import CommandBus
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
        config_revision="rev-1",
        motor_test_armed=False,
        configuration_restart_required=False,
        stop_requested=False,
        controlled_stop_requested=False,
        speed_override=None,
    )


def command(key: str, distance: float = 1.0) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="JOG",
        source="http",
        parameters={"axis": "x", "distance_mm": distance},
        idempotency_key=key,
    )


def test_completed_duplicate_is_returned_without_second_execution() -> None:
    bus = CommandBus(StateMachine(MachineState.READY), snapshot)
    calls = 0

    def handler(envelope: CommandEnvelope) -> CommandResult:
        nonlocal calls
        calls += 1
        return CommandResult(True, envelope.command_id, "COMPLETED", result={"ok": True})

    bus.register("JOG", handler)
    first = bus.submit(command("same-request"))
    second = bus.submit(command("same-request"))

    assert first.ok() and second.ok()
    assert calls == 1


def test_same_key_cannot_be_reused_for_different_motion() -> None:
    bus = CommandBus(StateMachine(MachineState.READY), snapshot)
    bus.register("JOG", lambda env: CommandResult(True, env.command_id, "COMPLETED"))
    bus.submit(command("reused", 1.0))

    conflict = bus.submit(command("reused", 2.0))

    assert not conflict.ok()
    assert conflict.error is not None
    assert conflict.error["code"] == "IDEMPOTENCY_CONFLICT"


def test_idempotency_storage_evicts_oldest_entry_at_capacity() -> None:
    bus = CommandBus(StateMachine(MachineState.READY), snapshot, idempotency_capacity=2)
    calls = 0

    def handler(envelope: CommandEnvelope) -> CommandResult:
        nonlocal calls
        calls += 1
        return CommandResult(True, envelope.command_id, "COMPLETED")

    bus.register("JOG", handler)
    bus.submit(command("one"))
    bus.submit(command("two"))
    bus.submit(command("three"))
    bus.submit(command("one"))
    assert calls == 4


def test_concurrent_duplicate_never_executes_twice() -> None:
    bus = CommandBus(StateMachine(MachineState.READY), snapshot)
    entered = threading.Event()
    release = threading.Event()
    calls = 0

    def handler(envelope: CommandEnvelope) -> CommandResult:
        nonlocal calls
        calls += 1
        entered.set()
        assert release.wait(timeout=1)
        return CommandResult(True, envelope.command_id, "COMPLETED")

    bus.register("JOG", handler)
    result_holder: list[CommandResult] = []
    worker = threading.Thread(target=lambda: result_holder.append(bus.submit(command("concurrent"))))
    worker.start()
    assert entered.wait(timeout=1)
    duplicate = bus.submit(command("concurrent"))
    release.set()
    worker.join(timeout=1)

    assert calls == 1
    assert duplicate.error is not None
    assert duplicate.error["code"] == "COMMAND_IN_PROGRESS"
    assert result_holder[0].ok()
