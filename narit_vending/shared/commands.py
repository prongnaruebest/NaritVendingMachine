"""CommandEnvelope and CommandResult — shared command contract.

Used by both the web process (to build commands) and the controller process
(to dispatch commands through the command bus).
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


def _new_id() -> str:
    return uuid.uuid4().hex


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Command types ──────────────────────────────────────────────────────────────

CommandType = Literal[
    "HOME_AXIS",
    "HOME_ALL",
    "JOG",
    "MOVE_TO",
    "MOVE_TO_LIMIT",
    "MOVE_TO_SLOT",
    "RUN_SLOT_SEQUENCE",
    "DISPENSE",
    "STOP",
    "E_STOP",
    "CLEAR_ALARM",
    "ARM_MOTOR_TEST",
    "DISARM_MOTOR_TEST",
    "RUN_MOTOR_TEST",
    "SET_SPEED",
    "SET_TIMER",
    "PLAN_MOVE",
    "VALIDATE_TARGET",
    "ARM_MOVE",
    "EXECUTE_ARMED_MOVE",
    "SAVE_SLOT",
    "SAVE_SLOT_FROM_CURRENT",
    "SAVE_CONFIG",
    "SCHEDULE_RESTART",
    "CONTROLLED_STOP",
    "DISABLE_MOTION",
    "ENABLE_MOTION",
    "RESET_NUCLEO_LINK",
    "RESET_XY_DRIVE_POWER",
    "CUT_XY_DRIVE_POWER",
    "RESTORE_XY_DRIVE_POWER",
    "CONFIGURE_DEMO",
    "VALIDATE_DEMO",
    "ARM_DEMO",
    "START_DEMO",
    "PAUSE_DEMO",
    "RESUME_DEMO",
    "STOP_DEMO",
]

CommandSource = Literal["http", "mqtt", "system"]


@dataclass(frozen=True)
class CommandMetadata:
    """Versioned request context that never carries motion authority."""

    schema_version: int = 1
    correlation_id: str = ""
    actor: str = ""
    client_revision: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError(f"Unsupported command metadata schema_version: {self.schema_version}")

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "CommandMetadata":
        payload = data or {}
        return cls(
            schema_version=int(payload.get("schema_version", 1)),
            correlation_id=str(payload.get("correlation_id", "")),
            actor=str(payload.get("actor", "")),
            client_revision=str(payload.get("client_revision", "")),
        )


@dataclass(frozen=True)
class CommandEnvelope:
    """Immutable command submitted to the controller command bus.

    Every command from HTTP, MQTT, or internal automation must be wrapped in
    a CommandEnvelope so that all sources pass through the same safety gate.
    """

    command_type: CommandType
    source: CommandSource
    parameters: dict[str, Any]
    command_id: str = field(default_factory=_new_id)
    idempotency_key: str = field(default_factory=_new_id)
    requested_at: str = field(default_factory=_now_iso)
    config_revision: str = ""
    metadata: CommandMetadata = field(default_factory=CommandMetadata)

    def __post_init__(self) -> None:
        if not isinstance(self.parameters, dict):
            raise TypeError("Command parameters must be an object")
        if not isinstance(self.metadata, CommandMetadata):
            object.__setattr__(self, "metadata", CommandMetadata.from_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CommandEnvelope":
        return cls(
            command_type=data["command_type"],
            source=data.get("source", "http"),
            parameters=dict(data.get("parameters", {})),
            command_id=data.get("command_id", _new_id()),
            idempotency_key=data.get("idempotency_key", _new_id()),
            requested_at=data.get("requested_at", _now_iso()),
            config_revision=data.get("config_revision", ""),
            metadata=CommandMetadata.from_dict(data.get("metadata")),
        )


@dataclass
class CommandResult:
    """Result returned from the controller after processing a CommandEnvelope."""

    accepted: bool
    command_id: str
    state: str  # "ACCEPTED" | "REJECTED" | "COMPLETED" | "FAILED" | "BUSY"
    reason: str | None = None
    result: Any = None  # arbitrary result payload
    started_at: str | None = None
    completed_at: str | None = None
    error: dict[str, Any] | None = None

    def ok(self) -> bool:
        return self.accepted and self.state in ("ACCEPTED", "COMPLETED")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok(),
            "accepted": self.accepted,
            "command_id": self.command_id,
            "state": self.state,
            "reason": self.reason,
            "result": self.result,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }

    @classmethod
    def rejected(
        cls,
        command_id: str,
        reason: str,
        *,
        code: str = "COMMAND_REJECTED",
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> "CommandResult":
        return cls(
            accepted=False,
            command_id=command_id,
            state="REJECTED",
            reason=reason,
            completed_at=_now_iso(),
            error={
                "code": code,
                "message": reason,
                "details": details or {},
                "retryable": retryable,
            },
        )

    @classmethod
    def busy(cls, command_id: str) -> "CommandResult":
        return cls(
            accepted=False,
            command_id=command_id,
            state="BUSY",
            reason="Machine is busy with another command",
            error={
                "code": "MACHINE_BUSY",
                "message": "Machine is busy with another command",
                "details": {},
                "retryable": True,
            },
        )

    @classmethod
    def accepted_async(cls, command_id: str) -> "CommandResult":
        """Return immediately when command is accepted but not yet completed."""
        return cls(
            accepted=True,
            command_id=command_id,
            state="ACCEPTED",
            started_at=_now_iso(),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CommandResult":
        return cls(
            accepted=bool(data.get("accepted", False)),
            command_id=str(data.get("command_id", "")),
            state=str(data.get("state", "UNKNOWN")),
            reason=data.get("reason"),
            result=data.get("result"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
        )
