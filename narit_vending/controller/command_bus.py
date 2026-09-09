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

import json
import logging
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

from .safety import SafetyInterlock
from .state_machine import StateMachine
from ..persistence.idempotency_repository import (
    IdempotencyRecord,
    IdempotencyRepository,
    InMemoryIdempotencyRepository,
)

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

    def __init__(
        self,
        state_machine: StateMachine,
        snapshot_fn: Callable[[], "MachineSnapshot"],
        *,
        idempotency_capacity: int = 256,
        idempotency_repository: IdempotencyRepository | None = None,
    ) -> None:
        self._state_machine = state_machine
        self._snapshot_fn = snapshot_fn
        self._safety = SafetyInterlock()
        self._motion_lock = threading.Lock()
        self._handlers: dict[str, Callable[["CommandEnvelope"], "CommandResult"]] = {}
        self._lock = threading.RLock()
        self._idempotency = idempotency_repository or InMemoryIdempotencyRepository(idempotency_capacity)
        self._idempotency_inflight: dict[str, str] = {}

    def register(self, command_type: str, handler: Callable[["CommandEnvelope"], "CommandResult"]) -> None:
        """Register a handler callable for a command type."""
        with self._lock:
            self._handlers[command_type] = handler
            _log.debug("Registered handler for %s", command_type)

    def submit(self, envelope: "CommandEnvelope") -> "CommandResult":
        """Deduplicate one logical request, then execute it through the safety gate."""
        from narit_vending.shared.commands import CommandResult

        key = envelope.idempotency_key
        fingerprint = self._fingerprint(envelope)
        with self._lock:
            cached = self._idempotency.get(key)
            if cached is not None:
                if cached.fingerprint != fingerprint:
                    return CommandResult.rejected(
                        envelope.command_id,
                        "Idempotency key was already used for a different command",
                        code="IDEMPOTENCY_CONFLICT",
                    )
                return CommandResult.from_dict(cached.result)
            inflight_fingerprint = self._idempotency_inflight.get(key)
            if inflight_fingerprint is not None:
                if inflight_fingerprint != fingerprint:
                    return CommandResult.rejected(
                        envelope.command_id,
                        "Idempotency key is in use by a different command",
                        code="IDEMPOTENCY_CONFLICT",
                    )
                return CommandResult.rejected(
                    envelope.command_id,
                    "Command with this idempotency key is already in progress",
                    code="COMMAND_IN_PROGRESS",
                    retryable=True,
                )
            self._idempotency_inflight[key] = fingerprint

        try:
            result = self._submit_once(envelope)
            if result.state != "BUSY":
                with self._lock:
                    self._idempotency.put(IdempotencyRecord(key, fingerprint, result.to_dict()))
            return result
        finally:
            with self._lock:
                self._idempotency_inflight.pop(key, None)

    @staticmethod
    def _fingerprint(envelope: "CommandEnvelope") -> str:
        return json.dumps(
            {
                "command_type": envelope.command_type,
                "source": envelope.source,
                "parameters": envelope.parameters,
                "config_revision": envelope.config_revision,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

    def _submit_once(self, envelope: "CommandEnvelope") -> "CommandResult":
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
            return CommandResult.rejected(
                envelope.command_id,
                decision.reason,
                code="SAFETY_INTERLOCK",
            )

        # ── Handler lookup ─────────────────────────────────────────────────────
        handler = self._handlers.get(cmd)
        if handler is None:
            _log.error("No handler registered for command type %s", cmd)
            return CommandResult.rejected(
                envelope.command_id,
                f"Unknown command type: {cmd}",
                code="UNKNOWN_COMMAND",
                details={"command_type": cmd},
            )

        # ── Priority commands bypass motion lock ───────────────────────────────
        is_priority = cmd in {
            "STOP", "E_STOP", "CLEAR_ALARM", "CONTROLLED_STOP", "SCHEDULE_RESTART",
            "DISABLE_MOTION", "RESET_NUCLEO_LINK", "RESET_XY_DRIVE_POWER",
            "CUT_XY_DRIVE_POWER", "RESTORE_XY_DRIVE_POWER", "STOP_DEMO",
        }
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
                error={
                    "code": "INTERNAL_HANDLER_ERROR",
                    "message": "The controller could not complete the command",
                    "details": {"command_type": envelope.command_type},
                    "retryable": False,
                },
            )
