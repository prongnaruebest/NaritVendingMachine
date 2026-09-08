"""Canonical normalization for legacy motion and Controller machine states."""

from __future__ import annotations

from .enums import MachineState


_LEGACY_STATES: dict[str, MachineState] = {
    "success": MachineState.READY,
    "ready": MachineState.READY,
    "idle": MachineState.NOT_READY,
    "not_ready": MachineState.NOT_READY,
    "homing": MachineState.HOMING,
    "moving": MachineState.MOVING,
    "alarm": MachineState.ALARM,
    "e_stop": MachineState.E_STOP,
    "stopped": MachineState.STOPPED,
}


def normalize_machine_state(
    raw_state: str,
    *,
    estop: bool,
    busy: bool,
    active_command: str | None,
    axes_homed: bool,
) -> MachineState:
    """Resolve legacy state plus authoritative safety/motion facts."""
    if estop:
        return MachineState.E_STOP
    if busy:
        command = str(active_command or "").lower()
        if command.startswith("home"):
            return MachineState.HOMING
        if command.startswith("dispense"):
            return MachineState.DISPENSING
        return MachineState.MOVING

    key = str(raw_state).strip().lower()
    if key == "idle":
        return MachineState.READY if axes_homed else MachineState.NOT_READY
    try:
        normalized = MachineState(key.upper())
    except ValueError:
        normalized = _LEGACY_STATES.get(key, MachineState.NOT_READY)
    if normalized == MachineState.READY and not axes_homed:
        return MachineState.NOT_READY
    return normalized
