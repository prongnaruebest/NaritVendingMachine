"""Atomic JSON repository for machine slot configuration."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any


class SlotRevisionConflict(RuntimeError):
    """The machine configuration changed after it was loaded."""


class JsonSlotRepository:
    """Update only the slots section while preserving all other configuration."""

    def __init__(self, config_path: str | Path) -> None:
        self.config_path = Path(config_path)
        self._lock = threading.RLock()

    def revision(self) -> str:
        if not self.config_path.exists():
            return "missing"
        return hashlib.sha256(self.config_path.read_bytes()).hexdigest()

    def load_all(self) -> dict[str, dict[str, Any]]:
        payload = self._read_payload()
        return {str(code): dict(value) for code, value in dict(payload.get("slots", {})).items()}

    def save_slot(
        self,
        slot_code: str,
        slot: dict[str, Any],
        *,
        expected_revision: str,
    ) -> str:
        code = str(slot_code)
        with self._lock:
            actual_revision = self.revision()
            if actual_revision != expected_revision:
                raise SlotRevisionConflict(
                    f"machine configuration changed: expected {expected_revision}, found {actual_revision}"
                )
            payload = self._read_payload()
            slots = payload.get("slots")
            if not isinstance(slots, dict) or code not in slots:
                raise KeyError(f"unknown slot '{code}'")
            slots[code] = {
                "x_mm": float(slot["x_mm"]),
                "y_mm": float(slot["y_mm"]),
                "z_mm": float(slot["z_mm"]),
                "product_name": str(slot.get("product_name", "")),
                "dispense_delay_ms": int(slot.get("dispense_delay_ms", 0)),
            }
            temporary = self.config_path.with_name(f".{self.config_path.name}.slot.tmp")
            temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, self.config_path)
            return self.revision()

    def _read_payload(self) -> dict[str, Any]:
        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("machine configuration root must be an object")
        return payload
