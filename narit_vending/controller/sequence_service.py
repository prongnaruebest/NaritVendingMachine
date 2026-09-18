"""Controller-owned slot sequence orchestration.

This module owns order and phase reporting only.  AxisController in
``motion.py`` remains the sole owner of GPIO and its move-time guards.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from narit_vending.domain.errors import ControlledStopError, EmergencyStopError, MotionError
from narit_vending.motion import SlotSequenceConfig


PhaseCallback = Callable[[str, dict[str, object]], None]


class SequenceService:
    """Execute the guarded 9-stage vending dispense cycle and sensor-based return home."""

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
        self._check_stop()

        axes = self._motion.controller.axes()
        if not all(getattr(axes[axis], "is_homed", False) for axis in ("x", "y", "z")):
            return {
                "ok": False,
                "error": "All axes must be homed before running slot sequence",
                "failed_phase": "VALIDATE_READY",
            }

        slot = self._motion.controller.config.slots.get(str(slot_code))
        if slot is None:
            return {"ok": False, "error": f"unknown slot '{slot_code}'", "failed_phase": "VALIDATE_SLOT"}

        def action() -> dict[str, object]:
            return self._execute(slot, speed_mm_s=speed_mm_s, phase_callback=phase_callback)

        return self._motion._run(f"slot_sequence_{slot_code}", action)

    def _execute(self, slot: Any, *, speed_mm_s: float | None, phase_callback: PhaseCallback | None) -> dict[str, object]:
        completed: list[str] = []
        cfg = getattr(self._motion.controller.config, "slot_sequence", None) or SlotSequenceConfig()
        controller = self._motion.controller
        speed = speed_mm_s or controller.speed_override
        axes = controller.axes()

        # Initial / Validation: Ensure Z is at Z_standby before lateral moves
        current_pos = controller.current_position()
        if abs(current_pos.get("z_mm", 0.0) - cfg.z_standby_mm) > self.POSITION_TOLERANCE_MM:
            self._check_stop()
            phase = "MOVE_Z_STANDBY"
            self._set_phase(phase, "z", f"Moving Z to standby position ({cfg.z_standby_mm:.1f} mm)", phase_callback)
            axes["z"].move_to_mm(cfg.z_standby_mm, speed_mm_s=speed)
            completed.append(phase)

        # Stage 1 - Move XY to Slot Target (Z stays at Z_standby)
        self._check_stop()
        phase = "MOVE_XY_TARGET"
        self._set_phase(phase, None, f"Stage 1: Moving XY to Slot {slot.code} ({slot.x_mm:.1f}, {slot.y_mm:.1f})", phase_callback)
        controller.move_to(x_mm=slot.x_mm, y_mm=slot.y_mm, speed_mm_s=speed)
        completed.append(phase)

        # Stage 2 - Extend Z into Slot (Min Limit Direction -> Z_pick)
        self._check_stop()
        phase = "EXTEND_Z_PICK"
        self._set_phase(phase, "z", f"Stage 2: Extending Z to pick position ({cfg.z_pick_mm:.1f} mm)", phase_callback)
        axes["z"].move_to_mm(cfg.z_pick_mm, speed_mm_s=speed)
        completed.append(phase)

        # Stage 3 - Y Lift & Dwell (Hook/Pickup)
        self._check_stop()
        y_max = getattr(axes["y"].config, "max_travel_mm", 2000.0)
        y_target = min(slot.y_mm + cfg.y_lift_delta_mm, y_max)
        phase = "Y_LIFT_PICK"
        self._set_phase(phase, "y", f"Stage 3: Lifting Y by +{cfg.y_lift_delta_mm:.1f} mm to hook product", phase_callback)
        axes["y"].move_to_mm(y_target, speed_mm_s=speed)
        completed.append(phase)

        phase = "HOLD_AT_PICK"
        self._set_phase(phase, None, f"Holding at pick position for {cfg.pick_hold_seconds:.1f} s", phase_callback)
        for _ in range(round(cfg.pick_hold_seconds / self.HOLD_POLL_SECONDS)):
            self._check_stop()
            time.sleep(self.HOLD_POLL_SECONDS)
        completed.append(phase)

        # Stage 4 - Retract Z to Standby
        self._check_stop()
        phase = "RETRACT_Z_STANDBY"
        self._set_phase(phase, "z", f"Stage 4: Retracting Z to standby ({cfg.z_standby_mm:.1f} mm)", phase_callback)
        axes["z"].move_to_mm(cfg.z_standby_mm, speed_mm_s=speed)
        completed.append(phase)

        # Stage 5 - Move XY to Parking Position
        self._check_stop()
        phase = "MOVE_XY_PARKING"
        self._set_phase(phase, None, f"Stage 5: Moving XY to parking position ({cfg.parking_x_mm:.1f}, {cfg.parking_y_mm:.1f})", phase_callback)
        controller.move_to(x_mm=cfg.parking_x_mm, y_mm=cfg.parking_y_mm, speed_mm_s=speed)
        completed.append(phase)

        # Stage 6 - Extend Z at Parking (Drop Position)
        self._check_stop()
        phase = "EXTEND_Z_DROP"
        self._set_phase(phase, "z", f"Stage 6: Extending Z to drop position ({cfg.z_drop_mm:.1f} mm)", phase_callback)
        axes["z"].move_to_mm(cfg.z_drop_mm, speed_mm_s=speed)
        completed.append(phase)

        # Trigger dispense output pulse if available
        if hasattr(self._motion, "activate_dispense") and callable(self._motion.activate_dispense):
            self._motion.activate_dispense()

        phase = "HOLD_AT_DROP"
        self._set_phase(phase, None, f"Holding at drop position for {cfg.drop_hold_seconds:.1f} s", phase_callback)
        for _ in range(round(cfg.drop_hold_seconds / self.HOLD_POLL_SECONDS)):
            self._check_stop()
            time.sleep(self.HOLD_POLL_SECONDS)
        completed.append(phase)

        # Stage 7 - Retract Z to Standby
        self._check_stop()
        phase = "RETRACT_Z_DROP"
        self._set_phase(phase, "z", f"Stage 7: Retracting Z to standby ({cfg.z_standby_mm:.1f} mm)", phase_callback)
        axes["z"].move_to_mm(cfg.z_standby_mm, speed_mm_s=speed)
        completed.append(phase)

        # Stage 8 - Return Home (All Axes in safe order)
        home_order = getattr(controller.config, "home_order", ("z", "y", "x"))
        for axis_name in home_order:
            self._check_stop()
            phase = f"HOME_{axis_name.upper()}"
            self._set_phase(phase, axis_name, f"Homing {axis_name.upper()} axis", phase_callback)
            controller.home_axis(axis_name, progress=self._motion._home_progress)
            completed.append(phase)

        home_position = controller.current_position()
        home_verification = self._home_verification(home_position)
        if not home_verification["home_reached"]:
            raise MotionError("Home position verification failed")

        self._set_phase("COMPLETED", None, "Slot sequence completed; all axes returned home", phase_callback)
        return {
            "slot_code": str(slot.code),
            "sequence": completed,
            "pick_hold_s": cfg.pick_hold_seconds,
            "drop_hold_s": cfg.drop_hold_seconds,
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
            state = (
                "moving"
                if (
                    phase.startswith("MOVE_")
                    or phase.startswith("EXTEND_")
                    or phase.startswith("RETRACT_")
                    or phase.startswith("Y_LIFT_")
                )
                else "homing"
                if phase.startswith("HOME_")
                else "running"
            )
            callback(state, {"phase": phase, "active_axis": axis, "message": message})

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
