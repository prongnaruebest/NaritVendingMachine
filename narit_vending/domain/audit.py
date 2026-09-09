"""Structured immutable audit event contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    occurred_at: str
    event_code: str
    correlation_id: str
    command_id: str
    category: str
    severity: str
    outcome: str
    source: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
