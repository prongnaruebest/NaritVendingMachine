"""Controller-owned slot sequence orchestration.

This module owns order and phase reporting only.  AxisController in
``motion.py`` remains the sole owner of GPIO and its move-time guards.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from narit_vending.motion import ControlledStopError, EmergencyStopError, MotionError


PhaseCallback = Callable[[str, dict[str, object]], None]


class SequenceService:
    """Execute the guarded X/Y/Z slot cycle and sensor-based return home."""

    HOLD_SECONDS = 3.0
    HOLD_POLL_SECONDS = 0.1
    POSITION_TOLERANCE_MM = 0.05

    def __init__(self, motion_service: Any) -> None:
        # Adapter around the existing Controller-owned MotionService while the
        # remaining legacy service is progressively decomposed.
        self._motion = motion_service

    def run(
        self,
        slot_code: str,
        *,
        speed_mm_s: float | None = None,
        request_id: str | None = None,
        phase_callback: PhaseCallback | None = None,
    ) -> dict[str, object]:
        slot = self._motion.controller.config.slots.get(str(slot_code))
        if slot is None:
            return {"ok": False, "error": f"unknown slot '{slot_code}'", "failed_phase": "VALIDATE_SLOT"}

        def action() -> dict[str, object]:
            return self._execute(slot, speed_mm_s=speed_mm_s, phase_callback=phase_callback)

        return self._motion._run(f"slot_sequence_{slot_code}", action)

    def _execute(self, slot: Any, *, speed_mm_s: float | None, phase_callback: PhaseCallback | None) -> dict[str, object]:
        completed: list[str] = []
        for axis_name in ("x", "y", "z"):
            self._check_stop()
            phase = f"MOVE_{axis_name.upper()}"
            self._set_phase(phase, axis_name, f"Moving {axis_name.upper()} axis to Slot {slot.code}", phase_callback)
            self._motion.controller.axes()[axis_name].move_to_mm(
                getattr(slot, f"{axis_name}_mm"),
                speed_mm_s=speed_mm_s or self._motion.controller.speed_override,
            )
            completed.append(phase)

        target_position = self._motion.controller.current_position()
        target_verification = self._target_verification(slot, target_position)
        if not target_verification["target_reached"]:
            raise MotionError("Target position verification failed")

        self._set_phase("DISPENSE", None, "Activating IRIV IO dispense output", phase_callback)
        self._motion.activate_dispense()
        completed.append("DISPENSE")

        self._set_phase("HOLD_AT_TARGET", None, "Holding at slot target for 3 seconds", phase_callback)
        for _ in range(round(self.HOLD_SECONDS / self.HOLD_POLL_SECONDS)):
            self._check_stop()
            time.sleep(self.HOLD_POLL_SECONDS)
        completed.append("HOLD_AT_TARGET")

        for axis_name in ("z", "y", "x"):
            self._check_stop()
            phase = f"HOME_{axis_name.upper()}"
            self._set_phase(phase, axis_name, f"Homing {axis_name.upper()} axis", phase_callback)
            self._motion.controller.home_axis(axis_name, progress=self._motion._home_progress)
            completed.append(phase)

        home_position = self._motion.controller.current_position()
        home_verification = self._home_verification(home_position)
        if not home_verification["home_reached"]:
            raise MotionError("Home position verification failed")

        self._set_phase("COMPLETED", None, "Slot sequence completed; all axes returned home", phase_callback)
        return {
            "slot_code": str(slot.code),
            "hold_s": int(self.HOLD_SECONDS),
            "sequence": completed,
            "target_verification": target_verification,
            "home_verification": home_verification,
        }

    def _set_phase(
        self,
        phase: str,
        axis: str | None,
        message: str,
        callback: PhaseCallback | None,
    ) -> None:
        self._motion.set_sequence_operation(phase, axis, message)
        if callback is not None:
            state = "moving" if phase.startswith("MOVE_") else "homing" if phase.startswith("HOME_") else "running"
            callback(state, {"phase": phase, "active_axis": axis})

    def _check_stop(self) -> None:
        if self._motion.controller.emergency_stop_active():
            raise EmergencyStopError("Emergency stop is active")
        if self._motion.controller.stop_requested():
            raise ControlledStopError("Sequence stopped before next stage")

    def _target_verification(self, slot: Any, actual: dict[str, float]) -> dict[str, object]:
        target = {axis: float(getattr(slot, f"{axis}_mm")) for axis in ("x", "y", "z")}
        measured = {axis: float(actual[f"{axis}_mm"]) for axis in ("x", "y", "z")}
        return {
            "target_reached": all(abs(measured[axis] - target[axis]) <= self.POSITION_TOLERANCE_MM for axis in target),
            "target_position_mm": {axis: round(value, 3) for axis, value in target.items()},
            "actual_position_mm": {axis: round(value, 3) for axis, value in measured.items()},
        }

    def _home_verification(self, actual: dict[str, float]) -> dict[str, object]:
        axes_homed = {axis: bool(self._motion.controller.axes()[axis].is_homed) for axis in ("x", "y", "z")}
        measured = {axis: float(actual[f"{axis}_mm"]) for axis in ("x", "y", "z")}
        return {
            "home_reached": all(axes_homed.values()) and all(abs(value) <= self.POSITION_TOLERANCE_MM for value in measured.values()),
            "home_position_mm": {axis: round(value, 3) for axis, value in measured.items()},
            "axes_homed": axes_homed,
        }
