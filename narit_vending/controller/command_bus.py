"""Command Bus — single dispatch point for all commands in the controller.

All commands submitted from any source (HTTP via IPC, MQTT via IPC, system)
flow through CommandBus.submit().  The bus:
  1. Checks safety via SafetyInterlock
  2. Acquires the single-flight motion lock
  3. Dispatches to the correct handler
  4. Updates state machine
  5. Returns a CommandResult

Priority commands (STOP, E_STOP, CLEAR_ALARM) bypass the single-flight lock
and are handled immediately.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

from .safety import SafetyInterlock
from .state_machine import StateMachine

if TYPE_CHECKING:
    from narit_vending.shared.commands import CommandEnvelope, CommandResult
    from narit_vending.shared.snapshot import MachineSnapshot

_log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CommandBus:
    """Thread-safe single-dispatch command bus.

    Handlers are registered by command type string.  The bus does not own GPIO
    or motion objects — those are owned by the registered handler callables.
    """

    def __init__(self, state_machine: StateMachine, snapshot_fn: Callable[[], "MachineSnapshot"]) -> None:
        self._state_machine = state_machine
        self._snapshot_fn = snapshot_fn
        self._safety = SafetyInterlock()
        self._motion_lock = threading.Lock()
        self._handlers: dict[str, Callable[["CommandEnvelope"], "CommandResult"]] = {}
        self._lock = threading.RLock()

    def register(self, command_type: str, handler: Callable[["CommandEnvelope"], "CommandResult"]) -> None:
        """Register a handler callable for a command type."""
        with self._lock:
            self._handlers[command_type] = handler
            _log.debug("Registered handler for %s", command_type)

    def submit(self, envelope: "CommandEnvelope") -> "CommandResult":
        """Submit a command envelope and return the result synchronously.

        This method blocks the calling thread until the command completes.
        For long-running commands (HOME, MOVE) this may take several seconds.
        The IPC server calls this in a thread pool worker.
        """
        from narit_vending.shared.commands import CommandResult

        cmd = envelope.command_type
        _log.info("CommandBus.submit: %s id=%s source=%s", cmd, envelope.command_id, envelope.source)

        # ── Safety evaluation ──────────────────────────────────────────────────
        snapshot = self._snapshot_fn()
        decision = self._safety.evaluate(envelope, snapshot)
        if not decision.allowed:
            _log.warning("Command %s rejected: %s", cmd, decision.reason)
            return CommandResult.rejected(envelope.command_id, decision.reason)

        # ── Handler lookup ─────────────────────────────────────────────────────
        handler = self._handlers.get(cmd)
        if handler is None:
            _log.error("No handler registered for command type %s", cmd)
            return CommandResult.rejected(envelope.command_id, f"Unknown command type: {cmd}")

        # ── Priority commands bypass motion lock ───────────────────────────────
        is_priority = cmd in {"STOP", "E_STOP", "CLEAR_ALARM", "CONTROLLED_STOP"}
        if is_priority:
            return self._dispatch(handler, envelope)

        # ── Normal commands require motion lock ───────────────────────────────
        acquired = self._motion_lock.acquire(blocking=False)
        if not acquired:
            _log.warning("Command %s rejected: machine busy", cmd)
            return CommandResult.busy(envelope.command_id)
        try:
            return self._dispatch(handler, envelope)
        finally:
            self._motion_lock.release()

    def _dispatch(
        self,
        handler: Callable[["CommandEnvelope"], "CommandResult"],
        envelope: "CommandEnvelope",
    ) -> "CommandResult":
        from narit_vending.shared.commands import CommandResult

        started = _now()
        try:
            result = handler(envelope)
            result.started_at = result.started_at or started
            result.completed_at = result.completed_at or _now()
            return result
        except Exception as exc:
            _log.exception("Handler exception for %s: %s", envelope.command_type, exc)
            return CommandResult(
                accepted=False,
                command_id=envelope.command_id,
                state="FAILED",
                reason=f"Internal handler error: {exc}",
                started_at=started,
                completed_at=_now(),
            )
