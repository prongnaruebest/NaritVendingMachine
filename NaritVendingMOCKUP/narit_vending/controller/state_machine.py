"""Machine state machine with explicit transition guards.

States mirror the Machine State Model in the Architecture Proposal.
Transitions are validated: attempting an invalid transition raises
StateMachineError so callers get a clear failure instead of a silent
state corruption.
"""

from __future__ import annotations

import logging
import threading
from enum import Enum
from typing import FrozenSet

_log = logging.getLogger(__name__)


class MachineState(str, Enum):
    """All valid machine states."""

    STARTING = "STARTING"
    CONFIG_REQUIRED = "CONFIG_REQUIRED"
    NOT_READY = "NOT_READY"
    HOMING = "HOMING"
    READY = "READY"
    MOVING = "MOVING"
    DISPENSING = "DISPENSING"
    MOTOR_TEST = "MOTOR_TEST"
    ALARM = "ALARM"
    E_STOP = "E_STOP"
    STOPPED = "STOPPED"


class StateMachineError(RuntimeError):
    pass


# Allowed transitions: {from_state: {to_states}}
_TRANSITIONS: dict[MachineState, FrozenSet[MachineState]] = {
    MachineState.STARTING: frozenset({
        MachineState.CONFIG_REQUIRED,
        MachineState.E_STOP,
        MachineState.NOT_READY,
    }),
    MachineState.CONFIG_REQUIRED: frozenset({
        MachineState.NOT_READY,  # after config fixed
        MachineState.E_STOP,
    }),
    MachineState.NOT_READY: frozenset({
        MachineState.HOMING,
        MachineState.E_STOP,
        MachineState.ALARM,
    }),
    MachineState.HOMING: frozenset({
        MachineState.READY,
        MachineState.ALARM,
        MachineState.E_STOP,
        MachineState.NOT_READY,  # abort home
    }),
    MachineState.READY: frozenset({
        MachineState.MOVING,
        MachineState.DISPENSING,
        MachineState.MOTOR_TEST,
        MachineState.E_STOP,
        MachineState.ALARM,
        MachineState.NOT_READY,  # after clear-alarm
    }),
    MachineState.MOVING: frozenset({
        MachineState.READY,
        MachineState.ALARM,
        MachineState.E_STOP,
    }),
    MachineState.DISPENSING: frozenset({
        MachineState.READY,
        MachineState.ALARM,
        MachineState.E_STOP,
    }),
    MachineState.MOTOR_TEST: frozenset({
        MachineState.NOT_READY,  # exit test — re-home required
        MachineState.ALARM,
        MachineState.E_STOP,
    }),
    MachineState.ALARM: frozenset({
        MachineState.NOT_READY,  # after reset + fault cleared
        MachineState.E_STOP,
    }),
    MachineState.E_STOP: frozenset({
        MachineState.NOT_READY,  # physical release + reset
    }),
    MachineState.STOPPED: frozenset({
        MachineState.NOT_READY,
        MachineState.E_STOP,
    }),
}

# Legacy string → MachineState mapping (for compatibility with existing motion.py set_state calls)
_LEGACY_MAP: dict[str, MachineState] = {
    "idle": MachineState.NOT_READY,
    "moving": MachineState.MOVING,
    "alarm": MachineState.ALARM,
    "success": MachineState.READY,
    "homing": MachineState.HOMING,
    "e_stop": MachineState.E_STOP,
    "stopped": MachineState.STOPPED,
    "ready": MachineState.READY,
}


class StateMachine:
    """Thread-safe machine state machine."""

    def __init__(self, initial: MachineState = MachineState.STARTING) -> None:
        self._state = initial
        self._lock = threading.RLock()

    @property
    def state(self) -> MachineState:
        with self._lock:
            return self._state

    def transition(self, new_state: MachineState | str) -> MachineState:
        """Attempt a state transition.  Returns new state on success.

        Accepts both MachineState enum values and legacy string values
        (idle, moving, alarm, success, homing) for backward compatibility
        during the migration period.
        """
        if isinstance(new_state, str):
            # Try enum name first, then legacy map
            try:
                new_state = MachineState(new_state.upper())
            except ValueError:
                new_state = _LEGACY_MAP.get(new_state.lower())
                if new_state is None:
                    raise StateMachineError(f"Unknown state string: {new_state!r}")

        with self._lock:
            allowed = _TRANSITIONS.get(self._state, frozenset())
            if new_state not in allowed:
                _log.error(
                    "Invalid state transition %s → %s (allowed: %s)",
                    self._state.value,
                    new_state.value,
                    ", ".join(s.value for s in allowed),
                )
                raise StateMachineError(
                    f"Cannot transition from {self._state.value} to {new_state.value}"
                )
            _log.info("State: %s → %s", self._state.value, new_state.value)
            self._state = new_state
            return self._state

    def force(self, new_state: MachineState) -> MachineState:
        """Force a state without checking transitions.

        Use ONLY for E-Stop or startup initialization where safety requires
        the state to change regardless of normal flow.
        """
        with self._lock:
            _log.warning("Force state: %s → %s", self._state.value, new_state.value)
            self._state = new_state
            return self._state

    def is_motion_allowed(self) -> bool:
        """Return True only when the machine is in READY state."""
        return self._state == MachineState.READY

    def is_homing_allowed(self) -> bool:
        return self._state == MachineState.NOT_READY

    def is_stopped(self) -> bool:
        return self._state in (MachineState.ALARM, MachineState.E_STOP, MachineState.STOPPED)

    def __repr__(self) -> str:
        return f"StateMachine(state={self._state.value!r})"
