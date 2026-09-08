from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic, sleep
from typing import Callable

if os.name != "posix" and "GPIOZERO_PIN_FACTORY" not in os.environ:
    os.environ["GPIOZERO_PIN_FACTORY"] = "mock"

from gpiozero import DigitalInputDevice, OutputDevice
from gpiozero.pins.mock import MockFactory

from .config_foundation import load_hardware_payload
from .domain.errors import (
    ActiveLimitError,
    ControlledStopError,
    EmergencyStopError,
    LimitTriggeredError,
    MotionError,
    NotHomedError,
    NucleoError,
    StopRequestedError,
    TravelBoundaryError,
)
from .domain.motion_math import (
    clamp_axis_speed_mm_s,
    effective_speed_limit_mm_s,
    mm_s_to_pulse_hz,
    pulse_hz_to_mm_s,
    pulse_hz_to_rpm,
    pulses_per_revolution,
)
from .domain.motion_plans import AxisMovePlan, CoordinatedMovePlan


_logger = logging.getLogger(__name__)

# Conservative fallback for a backend that does not advertise its MOVE-frame
# capability. NucleoLink exposes max_move_steps from the firmware handshake.
NUCLEO_MOVE_CHUNK_STEPS = 10_000


def _slot_sort_key(item: tuple[str, object]) -> tuple[int, int | str]:
    code = str(item[0])
    return (0, int(code)) if code.isdigit() else (1, code)


def _home_backoff_limit_steps(steps_per_mm: float) -> int:
    """Allow enough travel for a mechanical home switch to release.

    Two millimetres was too short for the installed sensor/bracket geometry and
    caused a false ``sensor did not release`` failure.  The move still stops as
    soon as the input releases; 10 mm is only a watchdog ceiling, not a forced
    move distance.
    """
    return max(1, int(round(10.0 * steps_per_mm)))


@dataclass(frozen=True)
class AxisConfig:
    name: str
    pulse_pin: int
    direction_pin: int
    head_limit_pin: int
    tail_limit_pin: int
    home_direction: int
    forward_direction: int
    steps_per_mm: float
    max_travel_mm: float
    max_speed_mm_s: float = 30.0
    default_speed_mm_s: float = 15.0
    settle_delay: float = 0.05
    jog_step_mm: float = 5.0
    enable_pin: int | None = None
    acceleration: float = 80.0
    deceleration: float = 80.0
    lead_screw_pitch_mm: float = 5.0
    motor_steps_per_rev: int = 200
    driver_microsteps: int = 10
    home_position_mm: float = 0.0
    max_pulse_hz: float = 50_000.0
    commissioned_max_speed_mm_s: float = 5.0
    homing_search_speed_mm_s: float = 5.0
    homing_latch_speed_mm_s: float = 1.0
    homing_timeout_s: float = 120.0
    drive_type: str = "lead_screw"
    nominal_travel_mm: float | None = None
    measured_travel_mm: float | None = None
    travel_safety_margin_mm: float = 5.0
    pulley_pitch_mm: float | None = None
    pulley_teeth: int | None = None

    def __post_init__(self) -> None:
        positive_values = {
            "steps_per_mm": self.steps_per_mm,
            "max_travel_mm": self.max_travel_mm,
            "max_speed_mm_s": self.max_speed_mm_s,
            "default_speed_mm_s": self.default_speed_mm_s,
            "lead_screw_pitch_mm": self.lead_screw_pitch_mm,
            "motor_steps_per_rev": self.motor_steps_per_rev,
            "driver_microsteps": self.driver_microsteps,
            "max_pulse_hz": self.max_pulse_hz,
            "commissioned_max_speed_mm_s": self.commissioned_max_speed_mm_s,
            "homing_search_speed_mm_s": self.homing_search_speed_mm_s,
            "homing_latch_speed_mm_s": self.homing_latch_speed_mm_s,
            "homing_timeout_s": self.homing_timeout_s,
        }
        for field_name, value in positive_values.items():
            if not math.isfinite(float(value)) or float(value) <= 0:
                raise MotionError(f"{self.name}: {field_name} must be a finite number greater than 0")
        if self.default_speed_mm_s > self.max_speed_mm_s:
            raise MotionError(f"{self.name}: default_speed_mm_s cannot exceed max_speed_mm_s")
        if self.home_direction not in (0, 1) or self.forward_direction not in (0, 1):
            raise MotionError(f"{self.name}: motor directions must be 0 or 1")
        if self.home_direction == self.forward_direction:
            raise MotionError(f"{self.name}: home_direction and forward_direction must be opposite")
        if not math.isfinite(self.home_position_mm) or not 0 <= self.home_position_mm <= self.max_travel_mm:
            raise MotionError(f"{self.name}: home_position_mm must be within configured travel")
        for field_name in ("max_pulse_hz", "commissioned_max_speed_mm_s", "homing_search_speed_mm_s", "homing_latch_speed_mm_s", "homing_timeout_s"):
            if not math.isfinite(float(getattr(self, field_name))) or float(getattr(self, field_name)) <= 0:
                raise MotionError(f"{self.name}: {field_name} must be greater than zero")
        pulse_limited_speed = self.max_pulse_hz / self.steps_per_mm
        if self.commissioned_max_speed_mm_s > min(self.max_speed_mm_s, pulse_limited_speed):
            raise MotionError(f"{self.name}: commissioned speed exceeds motor or pulse limit")
        if self.homing_search_speed_mm_s > min(self.max_speed_mm_s, pulse_limited_speed):
            raise MotionError(f"{self.name}: homing search speed exceeds motor or pulse limit")
        if self.homing_latch_speed_mm_s > self.homing_search_speed_mm_s:
            raise MotionError(f"{self.name}: homing latch speed exceeds search speed")
        if self.drive_type not in ("lead_screw", "timing_belt", "other"):
            raise MotionError(f"{self.name}: unsupported drive_type")
        for field_name in ("nominal_travel_mm", "measured_travel_mm"):
            value = getattr(self, field_name)
            if value is not None and (not math.isfinite(float(value)) or float(value) <= 0):
                raise MotionError(f"{self.name}: {field_name} must be greater than zero")
        if not math.isfinite(self.travel_safety_margin_mm) or self.travel_safety_margin_mm < 0:
            raise MotionError(f"{self.name}: travel_safety_margin_mm cannot be negative")
        if self.pulley_pitch_mm is not None and (not math.isfinite(self.pulley_pitch_mm) or self.pulley_pitch_mm <= 0):
            raise MotionError(f"{self.name}: pulley_pitch_mm must be greater than zero")
        if self.pulley_teeth is not None and self.pulley_teeth <= 0:
            raise MotionError(f"{self.name}: pulley_teeth must be greater than zero")

    @property
    def step_pin(self) -> int:
        return self.pulse_pin

    @property
    def dir_pin(self) -> int:
        return self.direction_pin

    @property
    def pulses_per_rev(self) -> int:
        return int(pulses_per_revolution(self.motor_steps_per_rev, self.driver_microsteps))

    def pulse_hz_to_rpm(self, pulse_hz: float) -> float:
        return pulse_hz_to_rpm(pulse_hz, self.pulses_per_rev)

    def pulse_hz_to_mm_s(self, pulse_hz: float) -> float:
        return pulse_hz_to_mm_s(pulse_hz, self.steps_per_mm)

    def mm_s_to_pulse_hz(self, speed_mm_s: float) -> float:
        return mm_s_to_pulse_hz(speed_mm_s, self.steps_per_mm)


@dataclass(frozen=True)
class SlotPosition:
    code: str
    x_mm: float
    y_mm: float
    z_mm: float
    product_name: str = ""
    dispense_delay_ms: int = 0

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "code": self.code,
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
            "z_mm": self.z_mm,
            "product_name": self.product_name,
            "dispense_delay_ms": self.dispense_delay_ms,
        }


@dataclass(frozen=True)
class MachineConfig:
    x: AxisConfig
    y: AxisConfig
    z: AxisConfig
    home_order: tuple[str, ...] = ("z", "y", "x")
    slots: dict[str, SlotPosition] = field(default_factory=dict)
    safe_z_mm: float = 10.0

    def __post_init__(self) -> None:
        if len(self.home_order) != 3 or set(self.home_order) != {"x", "y", "z"}:
            raise MotionError("home_order must contain x, y, and z exactly once")
        if not math.isfinite(self.safe_z_mm) or not 0 <= self.safe_z_mm <= self.z.max_travel_mm:
            raise MotionError(f"safe_z_mm must be within 0-{self.z.max_travel_mm:.2f} mm")
        limits = {"x": self.x.max_travel_mm, "y": self.y.max_travel_mm, "z": self.z.max_travel_mm}
        for code, slot in self.slots.items():
            for axis_name in ("x", "y", "z"):
                coordinate = float(getattr(slot, f"{axis_name}_mm"))
                if not math.isfinite(coordinate) or not 0 <= coordinate <= limits[axis_name]:
                    raise MotionError(
                        f"slot {code}: {axis_name}_mm must be within 0-{limits[axis_name]:.2f} mm"
                    )
            if slot.dispense_delay_ms < 0:
                raise MotionError(f"slot {code}: dispense_delay_ms cannot be negative")

    def to_dict(self) -> dict[str, object]:
        return {
            "axes": {
                "x": _axis_config_to_dict(self.x),
                "y": _axis_config_to_dict(self.y),
                "z": _axis_config_to_dict(self.z),
            },
            "home_order": list(self.home_order),
            "safe_z_mm": self.safe_z_mm,
            "slots": {
                code: {
                    "x_mm": slot.x_mm,
                    "y_mm": slot.y_mm,
                    "z_mm": slot.z_mm,
                    "product_name": slot.product_name,
                    "dispense_delay_ms": slot.dispense_delay_ms,
                }
                for code, slot in sorted(self.slots.items(), key=_slot_sort_key)
            },
        }


class AxisController:
    def __init__(
        self,
        config: AxisConfig,
        pulse: OutputDevice,
        direction: OutputDevice,
        head_limit: DigitalInputDevice,
        tail_limit: DigitalInputDevice,
        estop: DigitalInputDevice,
        stop_requested: Callable[[], bool],
        controlled_stop_requested: Callable[[], bool],
        enable: OutputDevice | None = None,
        motion_backend: Any | None = None,
    ) -> None:
        self.config = config
        self.pulse = pulse
        self.direction = direction
        self.head_limit = head_limit
        self.tail_limit = tail_limit
        self.estop = estop
        self.stop_requested = stop_requested
        self.controlled_stop_requested = controlled_stop_requested
        self.enable = enable
        self.motion_backend = motion_backend
        self.position_steps = 0
        self.is_homed = False
        if self.enable is not None:
            self.enable.on()

    @property
    def position_mm(self) -> float:
        return self.position_steps / self.config.steps_per_mm

    def mm_to_steps(self, distance_mm: float) -> int:
        return round(distance_mm * self.config.steps_per_mm)

    def steps_to_mm(self, steps: int) -> float:
        return steps / self.config.steps_per_mm

    def clamp_speed(self, speed_mm_s: float | None) -> float:
        requested = self.config.default_speed_mm_s if speed_mm_s is None else float(speed_mm_s)
        if not math.isfinite(requested) or requested <= 0:
            raise MotionError(f"{self.config.name}: speed_mm_s must be a finite number greater than 0")
        return clamp_axis_speed_mm_s(requested, speed_limit_mm_s=self._effective_speed_limit())

    def _effective_speed_limit(self) -> float:
        return effective_speed_limit_mm_s(
            max_speed_mm_s=self.config.max_speed_mm_s,
            commissioned_max_speed_mm_s=self.config.commissioned_max_speed_mm_s,
            max_pulse_hz=self.config.max_pulse_hz,
            pulses_per_mm=self.config.steps_per_mm,
        )

    def plan_relative_move(self, distance_mm: float, speed_mm_s: float | None = None, time_s: float | None = None) -> AxisMovePlan:
        if not math.isfinite(float(distance_mm)):
            raise MotionError(f"{self.config.name}: distance_mm must be finite")
        if distance_mm == 0:
            return AxisMovePlan(
                axis=self.config.name,
                current_mm=self.position_mm,
                target_mm=self.position_mm,
                distance_mm=0.0,
                direction=self.config.forward_direction,
                steps=0,
                speed_mm_s=0.0,
                duration_s=0.0,
            )

        steps = abs(self.mm_to_steps(distance_mm))
        direction = self.config.forward_direction if distance_mm > 0 else self.config.home_direction
        target_mm = self.position_mm + distance_mm
        self._guard_before_move(direction, steps if direction == self.config.forward_direction else -steps)
        duration_s = self._resolve_duration(abs(distance_mm), steps, speed_mm_s, time_s)
        planned_speed = 0.0 if duration_s == 0 else abs(distance_mm) / duration_s
        return AxisMovePlan(
            axis=self.config.name,
            current_mm=self.position_mm,
            target_mm=target_mm,
            distance_mm=distance_mm,
            direction=direction,
            steps=steps,
            speed_mm_s=planned_speed,
            duration_s=duration_s,
        )

    def plan_absolute_move(self, target_mm: float, speed_mm_s: float | None = None, time_s: float | None = None) -> AxisMovePlan:
        if not self.is_homed:
            raise NotHomedError(f"{self.config.name}: axis must be homed before move_to_mm")
        if not math.isfinite(float(target_mm)):
            raise MotionError(f"{self.config.name}: target must be finite")
        if target_mm < 0 or target_mm > self.config.max_travel_mm:
            raise TravelBoundaryError(
                f"{self.config.name}: target {target_mm:.2f} mm outside 0-{self.config.max_travel_mm:.2f} mm"
            )
        return self.plan_relative_move(target_mm - self.position_mm, speed_mm_s=speed_mm_s, time_s=time_s)

    def move_mm(self, distance_mm: float, speed_mm_s: float | None = None, time_s: float | None = None) -> int:
        plan = self.plan_relative_move(distance_mm, speed_mm_s=speed_mm_s, time_s=time_s)
        return self._execute_plan(plan)

    def move_to_mm(self, target_mm: float, speed_mm_s: float | None = None, time_s: float | None = None) -> int:
        plan = self.plan_absolute_move(target_mm, speed_mm_s=speed_mm_s, time_s=time_s)
        return self._execute_plan(plan)

    def seek_limit(self, endpoint: str, speed_mm_s: float | None = None) -> dict[str, object]:
        """Move until the selected physical limit input becomes active.

        Endpoint seeking deliberately ignores the software coordinate and
        configured travel boundary.  It is a sensor-finding operation, not a
        move to the configured 0/max coordinate.  A generous physical-search
        watchdog remains mandatory so a broken sensor cannot run forever.
        """
        if endpoint not in {"min", "max"}:
            raise MotionError(f"{self.config.name}: endpoint must be min or max")
        direction = self.config.home_direction if endpoint == "min" else self.config.forward_direction
        sensor = self.head_limit if endpoint == "min" else self.tail_limit
        if sensor.value:
            self.position_steps = 0 if endpoint == "min" else self.mm_to_steps(self.config.max_travel_mm)
            self.is_homed = True
            return {"axis": self.config.name, "endpoint": endpoint, "sensor": "already_active", "steps": 0}
        if self.estop.value or self.stop_requested():
            self._guard_before_move(direction, 0)

        speed = self.clamp_speed(speed_mm_s)
        speed_hz = max(10.0, min(self.config.max_pulse_hz, speed * self.config.steps_per_mm))
        # Search up to twice the configured stroke at the effective speed plus
        # a fixed allowance. This prevents the normal homing timeout from
        # ending a slow Min/Max calibration before the physical switch while
        # retaining a watchdog for missing or failed sensors.
        expected_stroke_s = self.config.max_travel_mm / max(speed, 0.001)
        seek_watchdog_s = max(self.config.homing_timeout_s, expected_stroke_s * 2.0 + 30.0)
        deadline = monotonic() + seek_watchdog_s
        moved = 0
        self.direction.value = bool(direction)
        if self.motion_backend is not None and getattr(self.motion_backend, "expected_protocol", 1) >= 2:
            segment_limit = max(1, int(getattr(self.motion_backend, "max_move_steps", NUCLEO_MOVE_CHUNK_STEPS)))
            while not sensor.value:
                # A STOP/E-STOP may arrive after the previous firmware frame
                # returned.  Never arm and submit another frame while the stop
                # latch is active; doing so used to leave seek_limit spinning
                # forever and kept the Controller busy.
                if self.estop.value:
                    raise EmergencyStopError(f"{self.config.name}: emergency stop active during limit seek")
                if self.stop_requested():
                    raise StopRequestedError(f"{self.config.name}: stop requested during limit seek")
                if monotonic() >= deadline:
                    raise LimitTriggeredError(
                        f"{self.config.name}: {endpoint} physical limit not reached within {seek_watchdog_s:.1f} seconds"
                    )
                try:
                    result = self.motion_backend.move(
                        axis=self.config.name,
                        direction=direction,
                        steps=segment_limit,
                        speed_hz=speed_hz,
                        timeout_s=min(seek_watchdog_s, segment_limit / speed_hz + 4.0),
                        stop_requested=lambda: bool(self.estop.value or self.stop_requested() or sensor.value),
                    )
                    moved += int(result.get("steps", segment_limit))
                    if result.get("stopped") and not sensor.value:
                        if self.estop.value:
                            raise EmergencyStopError(f"{self.config.name}: emergency stop active during limit seek")
                        raise StopRequestedError(f"{self.config.name}: stop requested during limit seek")
                except NucleoError:
                    if sensor.value:
                        break
                    raise
        else:
            half_period = 0.5 / speed_hz
            while not sensor.value:
                if monotonic() >= deadline:
                    raise LimitTriggeredError(
                        f"{self.config.name}: {endpoint} physical limit not reached within {seek_watchdog_s:.1f} seconds"
                    )
                self._guard_during_move(direction)
                self._pulse_once(half_period)
                moved += 1

        self.position_steps = 0 if endpoint == "min" else self.mm_to_steps(self.config.max_travel_mm)
        self.is_homed = True
        sleep(self.config.settle_delay)
        return {
            "axis": self.config.name,
            "endpoint": endpoint,
            "sensor": "triggered",
            "steps": moved,
            "speed_mm_s": speed,
            "software_travel_ignored": True,
            "watchdog_s": seek_watchdog_s,
        }

    def test_pulses(
        self,
        pulse_count: int,
        pulse_frequency_hz: float,
        direction_name: str,
        ignore_limits: bool = False,
    ) -> dict[str, object]:
        if pulse_count < 1:
            raise MotionError(f"{self.config.name}: pulse_count must be greater than 0")
        if not math.isfinite(pulse_frequency_hz) or pulse_frequency_hz <= 0:
            raise MotionError(f"{self.config.name}: pulse_frequency_hz must be greater than 0")
        if direction_name not in ("forward", "reverse"):
            raise MotionError(f"{self.config.name}: direction must be forward or reverse")

        direction = self.config.forward_direction if direction_name == "forward" else self.config.home_direction
        delta_steps = pulse_count if direction == self.config.forward_direction else -pulse_count
        if not ignore_limits:
            self._guard_before_move(direction, delta_steps)
        self.direction.value = bool(direction)

        if self.motion_backend is not None and getattr(self.motion_backend, "expected_protocol", 1) >= 2:
            try:
                def _stop_cond():
                    if self.estop.value:
                        return True
                    if self.stop_requested():
                        return True
                    if self.controlled_stop_requested():
                        return True
                    if not ignore_limits:
                        if direction == self.config.home_direction and self.head_limit.value:
                            return True
                        if direction != self.config.home_direction and self.tail_limit.value:
                            return True
                    return False

                nucleo_res = self.motion_backend.move(
                    axis=self.config.name,
                    direction=direction,
                    steps=pulse_count,
                    speed_hz=pulse_frequency_hz,
                    stop_requested=_stop_cond,
                )
                moved = int(nucleo_res.get("steps", pulse_count))
            finally:
                self.is_homed = False
            sleep(self.config.settle_delay)
            return {
                "axis": self.config.name,
                "direction": direction_name,
                "direction_level": direction,
                "pulse_count": moved,
                "pulse_frequency_hz": pulse_frequency_hz,
                "duration_s": moved / pulse_frequency_hz,
                "backend": "nucleo",
                "limits_ignored": ignore_limits,
            }

        half_period_s = 0.5 / pulse_frequency_hz
        moved = 0
        try:
            for index in range(pulse_count):
                if not ignore_limits and index % 5 == 0:
                    self._guard_during_move(direction)
                self._pulse_once(half_period_s)
                moved += 1
        finally:
            self.pulse.off()
            self.is_homed = False
        sleep(self.config.settle_delay)
        return {
            "axis": self.config.name,
            "direction": direction_name,
            "direction_level": direction,
            "pulse_count": moved,
            "pulse_frequency_hz": pulse_frequency_hz,
            "duration_s": moved / pulse_frequency_hz,
            "limits_ignored": ignore_limits,
        }

    def home(
        self,
        backoff_steps: int | None = None,
        max_steps: int = 200000,
        progress: Callable[[str], None] | None = None,
    ) -> int:
        _logger.info("Home %s: starting", self.config.name)
        if self.estop.value:
            raise EmergencyStopError(f"{self.config.name}: emergency stop is active")

        effective_backoff = (
            backoff_steps
            if backoff_steps is not None
            else _home_backoff_limit_steps(self.config.steps_per_mm)
        )

        # Homing has an independently commissioned search speed.  Normal Jog,
        # GOTO and slot moves remain capped by commissioned_max_speed_mm_s.
        homing_speed = min(
            self.config.homing_search_speed_mm_s,
            self.config.max_speed_mm_s,
            self.config.max_pulse_hz / self.config.steps_per_mm,
        )
        duration_s = max_steps / max(homing_speed * self.config.steps_per_mm, 1.0)
        search_deadline = monotonic() + self.config.homing_timeout_s
        self.direction.value = bool(self.config.home_direction)
        moved = 0
        limit_active = self.head_limit.value
        if progress is not None:
            progress("searching")

        if self.motion_backend is not None and getattr(self.motion_backend, "expected_protocol", 1) >= 2:
            speed_hz = max(10.0, min(self.config.max_pulse_hz, homing_speed * self.config.steps_per_mm))
            # Protocol v2 monitors E-stop, software stop, and the home input every
            # 80 ms while a MOVE is active. Use the firmware's full move window
            # instead of flooding its serial task with 10 MOVE commands/second.
            chunk_steps = 10_000
            while not limit_active:
                if monotonic() >= search_deadline:
                    raise LimitTriggeredError(f"{self.config.name}: home sensor not reached within {self.config.homing_timeout_s:g} seconds")
                if self.estop.value:
                    raise EmergencyStopError(f"{self.config.name}: emergency stop triggered during homing")
                if self.stop_requested():
                    raise StopRequestedError(f"{self.config.name}: stop requested during homing")
                try:
                    res = self.motion_backend.move(
                        axis=self.config.name,
                        direction=self.config.home_direction,
                        steps=chunk_steps,
                        speed_hz=speed_hz,
                        stop_requested=lambda: bool(self.estop.value or self.stop_requested() or self.head_limit.value),
                    )
                    chunk_moved = int(res.get("steps", chunk_steps))
                    moved += chunk_moved
                except NucleoError:
                    if self.head_limit.value:
                        break
                    raise
                limit_active = self.head_limit.value
                if limit_active or chunk_moved < chunk_steps:
                    break

            sleep(self.config.settle_delay)
            if effective_backoff > 0:
                if progress is not None:
                    progress("backoff")
                release_direction = 1 - self.config.home_direction
                released = 0
                while self.head_limit.value and released < effective_backoff:
                    if self.estop.value:
                        raise EmergencyStopError(f"{self.config.name}: emergency stop triggered during homing backoff")
                    try:
                        res = self.motion_backend.move(
                            axis=self.config.name,
                            direction=release_direction,
                            steps=min(chunk_steps, effective_backoff - released),
                            speed_hz=speed_hz,
                            stop_requested=lambda: bool(self.estop.value or self.stop_requested() or not self.head_limit.value),
                        )
                        chunk_released = int(res.get("steps", chunk_steps))
                        released += chunk_released
                    except NucleoError:
                        if not self.head_limit.value:
                            break
                        raise
                    if not self.head_limit.value:
                        break
                sleep(self.config.settle_delay)
                if self.head_limit.value:
                    raise LimitTriggeredError(
                        f"{self.config.name}: home sensor did not release after {effective_backoff} backoff steps"
                    )

                if progress is not None:
                    progress("latching")
                latch_speed_hz = max(10.0, min(self.config.max_pulse_hz, self.config.homing_latch_speed_mm_s * self.config.steps_per_mm))
                latch_window = max(effective_backoff * 2, 1)
                try:
                    self.motion_backend.move(
                        axis=self.config.name,
                        direction=self.config.home_direction,
                        steps=min(latch_window, 10_000),
                        speed_hz=latch_speed_hz,
                        stop_requested=lambda: bool(self.estop.value or self.stop_requested() or self.head_limit.value),
                    )
                except NucleoError:
                    if not self.head_limit.value:
                        raise
                if not self.head_limit.value:
                    raise LimitTriggeredError(f"{self.config.name}: home sensor not found during precision latch")

            self.position_steps = 0
            self.is_homed = True
            if progress is not None:
                progress("completed")
            _logger.info("Home %s: complete (%d steps via nucleo)", self.config.name, moved)
            return moved

        half_periods = _build_half_periods(min(max_steps, 10_000), min(duration_s, 10.0), ramp_ratio=0.8)
        self.direction.value = bool(self.config.home_direction)
        moved = 0
        limit_active = self.head_limit.value
        if progress is not None:
            progress("searching")

        while not limit_active:
            if monotonic() >= search_deadline:
                raise LimitTriggeredError(f"{self.config.name}: home sensor not reached within {self.config.homing_timeout_s:g} seconds")
            if moved % 10 == 0:
                if self.estop.value:
                    self.stop()
                    raise EmergencyStopError(f"{self.config.name}: emergency stop triggered during homing")
                if self.stop_requested():
                    self.stop()
                    raise StopRequestedError(f"{self.config.name}: stop requested during homing")
                limit_active = self.head_limit.value
                if limit_active:
                    break
            self._pulse_once(half_periods[min(moved, len(half_periods) - 1)])
            moved += 1

        sleep(self.config.settle_delay)

        if effective_backoff > 0:
            if progress is not None:
                progress("backoff")
            release_direction = 1 - self.config.home_direction
            self.direction.value = bool(release_direction)
            released = 0
            while self.head_limit.value and released < effective_backoff:
                if released % 10 == 0:
                    self._guard_during_move(release_direction)
                self._pulse_once(half_periods[min(released, len(half_periods) - 1)])
                released += 1
            sleep(self.config.settle_delay)
            if self.head_limit.value:
                raise LimitTriggeredError(
                    f"{self.config.name}: home sensor did not release after {effective_backoff} backoff steps"
                )

            if progress is not None:
                progress("latching")
            self.direction.value = bool(self.config.home_direction)
            latch_half_period = 0.5 / max(10.0, self.config.homing_latch_speed_mm_s * self.config.steps_per_mm)
            latch_moved = 0
            while not self.head_limit.value and latch_moved < max(effective_backoff * 2, 1):
                self._guard_during_move(self.config.home_direction)
                self._pulse_once(latch_half_period)
                latch_moved += 1
            if not self.head_limit.value:
                raise LimitTriggeredError(f"{self.config.name}: home sensor not found during precision latch")

        self.position_steps = 0
        self.is_homed = True
        if progress is not None:
            progress("completed")
        _logger.info("Home %s: complete (%d steps)", self.config.name, moved)
        return moved

    def stop(self) -> None:
        self.pulse.off()

    def status(self) -> dict[str, int | float | bool]:
        return {
            "position_steps": self.position_steps,
            "position_mm": round(self.position_mm, 3),
            "is_homed": self.is_homed,
            "head_limit": bool(self.head_limit.value),
            "tail_limit": bool(self.tail_limit.value),
            "estop": bool(self.estop.value),
        }

    def _resolve_duration(
        self,
        distance_mm: float,
        steps: int,
        speed_mm_s: float | None,
        time_s: float | None,
    ) -> float:
        if steps == 0 or distance_mm == 0:
            return 0.0
        if time_s is not None:
            duration_s = float(time_s)
            if not math.isfinite(duration_s) or duration_s <= 0:
                raise MotionError(f"{self.config.name}: time_s must be a finite number greater than 0")
            required_speed = distance_mm / duration_s
            effective_max = self._effective_speed_limit()
            if required_speed > effective_max:
                raise MotionError(
                    f"{self.config.name}: requested {required_speed:.2f} mm/s exceeds commissioned limit {effective_max:.2f} mm/s"
                )
            return duration_s

        clamped_speed = self.clamp_speed(speed_mm_s)
        return distance_mm / clamped_speed

    def _execute_plan(self, plan: AxisMovePlan) -> int:
        if plan.steps == 0:
            return 0

        self.direction.value = bool(plan.direction)

        if self.motion_backend is not None and getattr(self.motion_backend, "expected_protocol", 1) >= 2:
            speed_hz = plan.steps / plan.duration_s if plan.duration_s > 0 else (self.config.steps_per_mm * self.config.default_speed_mm_s)
            protocol_cap_hz = 50_000.0 if getattr(self.motion_backend, "expected_protocol", 1) >= 3 else 1_000.0
            speed_hz = max(10.0, min(protocol_cap_hz, speed_hz))

            stop_context = {"reason": ""}

            def _stop_cond():
                if self.estop.value:
                    stop_context["reason"] = "emergency stop"
                    return True
                if self.stop_requested():
                    stop_context["reason"] = "stop requested"
                    return True
                if self.controlled_stop_requested():
                    stop_context["reason"] = "controlled jog release"
                    return True
                if plan.direction == self.config.home_direction and self.head_limit.value:
                    stop_context["reason"] = "Min limit triggered"
                    return True
                if plan.direction != self.config.home_direction and self.tail_limit.value:
                    stop_context["reason"] = "Max limit triggered"
                    return True
                return False

            segment_limit = max(
                1,
                int(getattr(self.motion_backend, "max_move_steps", NUCLEO_MOVE_CHUNK_STEPS)),
            )
            moved = 0
            remaining = plan.steps
            while remaining > 0:
                # Re-check all software and physical stop conditions between
                # firmware frames as well as while each frame is executing.
                if _stop_cond():
                    self._guard_during_move(plan.direction)
                    raise StopRequestedError(f"{self.config.name}: motion stopped before next USB move segment")

                chunk_steps = min(segment_limit, remaining)
                chunk_duration_s = chunk_steps / speed_hz
                res = self.motion_backend.move(
                    axis=self.config.name,
                    direction=plan.direction,
                    steps=chunk_steps,
                    speed_hz=speed_hz,
                    timeout_s=chunk_duration_s + 4.0,
                    stop_requested=_stop_cond,
                )
                completed = int(res.get("steps", chunk_steps))
                if completed < 0 or completed > chunk_steps:
                    raise MotionError(
                        f"{self.config.name}: invalid completed step count {completed} for {chunk_steps}-step segment"
                    )
                self.position_steps += completed if plan.direction == self.config.forward_direction else -completed
                moved += completed
                remaining -= completed
                stopped = bool(res.get("stopped"))
                stop_reason = stop_context["reason"]
                if stopped and (stop_reason == "controlled jog release" or self.controlled_stop_requested()):
                    # The release flag may be cleared by the request lifecycle
                    # before the USB worker returns. Preserve the reason observed
                    # inside the worker so a normal jog release never becomes a
                    # latched incomplete-segment alarm.
                    raise ControlledStopError(f"{self.config.name}: jog stopped when hold control was released")
                if stopped and stop_reason in {"Min limit triggered", "Max limit triggered"}:
                    # A directional end-stop is a recoverable endpoint, not a
                    # loss of machine reference.  Snap the logical coordinate
                    # to the known physical endpoint and reject only further
                    # motion into that switch.  Raising ActiveLimitError keeps
                    # MotionService from latching the all-axis software STOP,
                    # so the operator can move away immediately.
                    if self.is_homed:
                        self.position_steps = (
                            0
                            if plan.direction == self.config.home_direction
                            else self.mm_to_steps(self.config.max_travel_mm)
                        )
                    away = "positive" if plan.direction == self.config.home_direction else "negative"
                    raise ActiveLimitError(
                        f"{self.config.name}: {stop_reason}; move in the {away} direction"
                    )
                if stopped and stop_reason == "emergency stop":
                    self.is_homed = False
                    raise EmergencyStopError(f"{self.config.name}: emergency stop triggered")
                if stopped and stop_reason == "stop requested":
                    self.is_homed = False
                    raise StopRequestedError(f"{self.config.name}: stop requested")
                if completed != chunk_steps:
                    raise MotionError(
                        f"{self.config.name}: incomplete USB move segment ({completed}/{chunk_steps} steps)"
                        + (f"; stop reason: {stop_reason}" if stop_reason else "")
                    )
            sleep(self.config.settle_delay)
            return moved

        half_periods = _build_half_periods(plan.steps, plan.duration_s, ramp_ratio=1.6)
        moved = 0
        controlled_remaining: int | None = None
        controlled_total = 0
        for index, half_period in enumerate(half_periods):
            if index % 5 == 0:
                self._guard_during_move(plan.direction)
            if controlled_remaining is None and self.controlled_stop_requested():
                controlled_remaining = min(50, plan.steps - index)
                controlled_total = controlled_remaining
            stop_scale = 1.0
            if controlled_remaining is not None:
                stop_scale = 1.0 + (3.0 * (1.0 - controlled_remaining / max(controlled_total, 1)))
            self._pulse_once(half_period * stop_scale)
            self.position_steps += 1 if plan.direction == self.config.forward_direction else -1
            moved += 1
            if controlled_remaining is not None:
                controlled_remaining -= 1
                if controlled_remaining <= 0:
                    self.stop()
                    raise ControlledStopError(f"{self.config.name}: controlled stop completed")
        sleep(self.config.settle_delay)
        return moved

    def _pulse_once(self, half_period_s: float) -> None:
        self.pulse.on()
        sleep(half_period_s)
        self.pulse.off()
        sleep(half_period_s)

    def _guard_before_move(self, direction: int, delta_steps: int) -> None:
        if self.estop.value:
            raise EmergencyStopError(f"{self.config.name}: emergency stop is active")
        if self.stop_requested():
            raise StopRequestedError(f"{self.config.name}: stop requested")
        if direction == self.config.home_direction and self.head_limit.value:
            raise ActiveLimitError(f"{self.config.name}: Min limit is active; jog in the positive direction")
        if direction != self.config.home_direction and self.tail_limit.value:
            raise ActiveLimitError(f"{self.config.name}: Max limit is active; jog in the negative direction")
        if self.is_homed:
            target_steps = self.position_steps + delta_steps
            max_steps = self.mm_to_steps(self.config.max_travel_mm)
            if target_steps < 0 or target_steps > max_steps:
                raise TravelBoundaryError(
                    f"{self.config.name}: target exceeds configured travel 0-{self.config.max_travel_mm:.2f} mm"
                )

    def _guard_during_move(self, direction: int) -> None:
        if self.estop.value:
            self.stop()
            self.is_homed = False
            raise EmergencyStopError(f"{self.config.name}: emergency stop triggered")
        if self.stop_requested():
            self.stop()
            self.is_homed = False
            raise StopRequestedError(f"{self.config.name}: stop requested")
        if direction == self.config.home_direction and self.head_limit.value:
            self.stop()
            if self.is_homed:
                self.position_steps = 0
            raise ActiveLimitError(f"{self.config.name}: Min limit reached; move in the positive direction")
        if direction != self.config.home_direction and self.tail_limit.value:
            self.stop()
            if self.is_homed:
                self.position_steps = self.mm_to_steps(self.config.max_travel_mm)
            raise ActiveLimitError(f"{self.config.name}: Max limit reached; move in the negative direction")


class MotionController:
    def __init__(
        self,
        x: AxisController,
        y: AxisController,
        z: AxisController,
        estop: DigitalInputDevice,
        config: MachineConfig,
        led_idle: OutputDevice | None = None,
        led_moving: OutputDevice | None = None,
        led_success: OutputDevice | None = None,
        alarm_warning: OutputDevice | None = None,
        alarm_buzzer: OutputDevice | None = None,
    ) -> None:
        self.x = x
        self.y = y
        self.z = z
        self.estop = estop
        self.config = config
        self._stop_requested = False
        self._controlled_stop_requested = False
        self.led_idle = led_idle
        self.led_moving = led_moving
        self.led_success = led_success
        self.alarm_warning = alarm_warning
        self.alarm_buzzer = alarm_buzzer
        self.speed_override: float | None = None
        self.timer_seconds: float = 0.0
        self.last_plan: CoordinatedMovePlan | None = None
        self._state_name = "idle"
        self.set_state("idle")

    def axes(self) -> dict[str, AxisController]:
        return {"x": self.x, "y": self.y, "z": self.z}

    def home_axis(self, axis_name: str, progress: Callable[[str, str], None] | None = None) -> None:
        axis = self.axes()[axis_name.lower()]
        axis.home(progress=(lambda phase: progress(axis.config.name, phase)) if progress is not None else None)
        if axis.config.home_position_mm > 0:
            if progress is not None:
                progress(axis.config.name, "positioning")
            try:
                axis.move_to_mm(axis.config.home_position_mm, speed_mm_s=axis.config.commissioned_max_speed_mm_s)
            except Exception:
                axis.is_homed = False
                raise
        if progress is not None:
            progress(axis.config.name, "passed")

    def home_all(self, progress: Callable[[str, str], None] | None = None) -> None:
        backend_protocol = getattr(self.x.motion_backend, "expected_protocol", 1) if self.x.motion_backend is not None else 1
        if (
            self.x.motion_backend is not None
            and isinstance(backend_protocol, (int, float))
            and backend_protocol >= 3
            and hasattr(self.x.motion_backend, "home_parallel")
        ):
            axes = self.axes()
            plans = {}
            for name, axis in axes.items():
                if progress is not None:
                    progress(name, "searching")
                plans[name] = {
                    "direction": axis.config.home_direction,
                    "speed_hz": min(axis.config.max_pulse_hz, axis.config.homing_search_speed_mm_s * axis.config.steps_per_mm),
                    "limit": lambda current=axis: current.head_limit.value,
                    "abort": lambda current=axis: bool(current.estop.value or current.stop_requested()),
                    "timeout_s": axis.config.homing_timeout_s,
                }
            self.x.motion_backend.home_parallel(plans)
            for name, axis in axes.items():
                axis.home(progress=(lambda phase, current=name: progress(current, phase)) if progress is not None else None)
                if axis.config.home_position_mm > 0:
                    if progress is not None:
                        progress(name, "positioning")
                    try:
                        axis.move_to_mm(axis.config.home_position_mm, speed_mm_s=axis.config.commissioned_max_speed_mm_s)
                    except Exception:
                        axis.is_homed = False
                        raise
                if progress is not None:
                    progress(name, "passed")
            return
        for axis_name in self.config.home_order:
            self.home_axis(axis_name, progress=progress)

    def move_by_mm(
        self,
        x_mm: float = 0,
        y_mm: float = 0,
        z_mm: float = 0,
        speed_mm_s: float | None = None,
        time_s: float | None = None,
    ) -> CoordinatedMovePlan:
        target = {}
        if x_mm:
            target["x"] = self.x.position_mm + x_mm
        if y_mm:
            target["y"] = self.y.position_mm + y_mm
        if z_mm:
            target["z"] = self.z.position_mm + z_mm
        return self.move_to(
            x_mm=target.get("x"),
            y_mm=target.get("y"),
            z_mm=target.get("z"),
            speed_mm_s=speed_mm_s,
            time_s=time_s,
        )

    def plan_move(
        self,
        x_mm: float | None = None,
        y_mm: float | None = None,
        z_mm: float | None = None,
        speed_mm_s: float | None = None,
        time_s: float | None = None,
    ) -> CoordinatedMovePlan:
        effective_speed = speed_mm_s if speed_mm_s is not None else self.speed_override

        raw_targets = {"x": x_mm, "y": y_mm, "z": z_mm}
        included_axes = {name: value for name, value in raw_targets.items() if value is not None}
        if not included_axes:
            raise MotionError("At least one target axis must be provided")

        if len(included_axes) == 1:
            axis_name, target_mm = next(iter(included_axes.items()))
            plan = self.axes()[axis_name].plan_absolute_move(target_mm, speed_mm_s=effective_speed, time_s=time_s)
            mode = "time" if time_s is not None else "speed"
            return CoordinatedMovePlan(axes={axis_name: plan}, duration_s=plan.duration_s, mode=mode)

        for axis_name, target_mm in included_axes.items():
            axis = self.axes()[axis_name]
            if not axis.is_homed:
                raise NotHomedError(f"{axis_name}: axis must be homed before coordinated move")
            if target_mm < 0 or target_mm > axis.config.max_travel_mm:
                raise MotionError(
                    f"{axis_name}: target {target_mm:.2f} mm outside 0-{axis.config.max_travel_mm:.2f} mm"
                )

        distances = {
            name: included_axes[name] - self.axes()[name].position_mm
            for name in included_axes
        }
        max_distance = max(abs(distance) for distance in distances.values())
        if max_distance == 0:
            return CoordinatedMovePlan(axes={}, duration_s=0.0, mode="speed")

        if time_s is not None:
            duration_s = float(time_s)
            if not math.isfinite(duration_s) or duration_s <= 0:
                raise MotionError("time_s must be a finite number greater than 0")
            mode = "time"
        else:
            base_speed = effective_speed
            if base_speed is None:
                base_speed = max(
                    self.axes()[axis_name].config.default_speed_mm_s
                    for axis_name in included_axes
                )
            base_speed = float(base_speed)
            if not math.isfinite(base_speed) or base_speed <= 0:
                raise MotionError("speed_mm_s must be a finite number greater than 0")
            duration_s = max_distance / base_speed
            mode = "speed"

        plans: dict[str, AxisMovePlan] = {}
        for axis_name, target_mm in included_axes.items():
            distance_mm = distances[axis_name]
            axis = self.axes()[axis_name]
            required_speed = abs(distance_mm) / duration_s if duration_s > 0 else 0.0
            effective_max = min(axis.config.max_speed_mm_s, axis.config.commissioned_max_speed_mm_s, axis.config.max_pulse_hz / axis.config.steps_per_mm)
            if required_speed > effective_max:
                raise MotionError(
                    f"{axis_name}: requested {required_speed:.2f} mm/s exceeds commissioned limit {effective_max:.2f} mm/s"
                )
            plans[axis_name] = axis.plan_absolute_move(target_mm, speed_mm_s=required_speed, time_s=duration_s)

        return CoordinatedMovePlan(axes=plans, duration_s=duration_s, mode=mode)

    def move_to(
        self,
        x_mm: float | None = None,
        y_mm: float | None = None,
        z_mm: float | None = None,
        speed_mm_s: float | None = None,
        time_s: float | None = None,
    ) -> CoordinatedMovePlan:
        plan = self.plan_move(x_mm=x_mm, y_mm=y_mm, z_mm=z_mm, speed_mm_s=speed_mm_s, time_s=time_s)
        if not plan.axes:
            self.last_plan = plan
            return plan

        if len(plan.axes) == 1:
            single_plan = next(iter(plan.axes.values()))
            self.axes()[single_plan.axis]._execute_plan(single_plan)
            self.last_plan = plan
            return plan

        self._execute_coordinated_plan(plan)
        self.last_plan = plan
        return plan

    def current_position(self) -> dict[str, float]:
        return {
            "x_mm": round(self.x.position_mm, 3),
            "y_mm": round(self.y.position_mm, 3),
            "z_mm": round(self.z.position_mm, 3),
        }

    def move_to_slot(self, slot_code: str, speed_mm_s: float | None = None, time_s: float | None = None) -> SlotPosition:
        slot = self.config.slots.get(str(slot_code))
        if slot is None:
            raise MotionError(f"unknown slot '{slot_code}'")

        safe_z = min(self.config.safe_z_mm, self.z.config.max_travel_mm)
        if self.z.is_homed and self.z.position_mm < safe_z:
            self.z.move_to_mm(safe_z, speed_mm_s=speed_mm_s or self.speed_override)

        self.move_to(
            x_mm=slot.x_mm,
            y_mm=slot.y_mm,
            speed_mm_s=speed_mm_s or self.speed_override,
            time_s=time_s,
        )
        # A slot on the same physical Z step needs no firmware command.  This
        # explicit check prevents a no-op Z phase from being treated as a
        # rejected zero-step MOVE by any current or future motion backend.
        if self.z.mm_to_steps(slot.z_mm) != self.z.position_steps:
            self.z.move_to_mm(slot.z_mm, speed_mm_s=speed_mm_s or self.speed_override)
        return slot

    def update_slot(
        self,
        slot_code: str,
        x_mm: float,
        y_mm: float,
        z_mm: float,
        product_name: str | None = None,
        dispense_delay_ms: int | None = None,
    ) -> None:
        code = str(slot_code)
        if code not in self.config.slots:
            raise MotionError(f"unknown slot '{slot_code}'")
        coordinates = {"x": float(x_mm), "y": float(y_mm), "z": float(z_mm)}
        for axis_name, coordinate in coordinates.items():
            axis = self.axes()[axis_name]
            if not math.isfinite(coordinate) or coordinate < 0 or coordinate > axis.config.max_travel_mm:
                raise MotionError(
                    f"slot {code}: {axis_name}_mm must be within 0-{axis.config.max_travel_mm:.2f} mm"
                )
        if dispense_delay_ms is not None and dispense_delay_ms < 0:
            raise MotionError(f"slot {code}: dispense_delay_ms cannot be negative")
        existing = self.config.slots[code]
        new_slots = dict(self.config.slots)
        new_slots[code] = SlotPosition(
            code=code,
            x_mm=coordinates["x"],
            y_mm=coordinates["y"],
            z_mm=coordinates["z"],
            product_name=product_name if product_name is not None else existing.product_name,
            dispense_delay_ms=dispense_delay_ms if dispense_delay_ms is not None else existing.dispense_delay_ms,
        )
        self.config = MachineConfig(
            x=self.config.x,
            y=self.config.y,
            z=self.config.z,
            home_order=self.config.home_order,
            slots=new_slots,
            safe_z_mm=self.config.safe_z_mm,
        )

    def request_stop(self) -> None:
        self._stop_requested = True
        for axis in self.axes().values():
            axis.stop()

    def request_controlled_stop(self) -> None:
        self._controlled_stop_requested = True

    def clear_stop(self) -> None:
        self._stop_requested = False
        self._controlled_stop_requested = False

    def stop_requested(self) -> bool:
        return self._stop_requested

    def controlled_stop_requested(self) -> bool:
        return self._controlled_stop_requested

    def clear_controlled_stop(self) -> None:
        self._controlled_stop_requested = False

    def emergency_stop_active(self) -> bool:
        return bool(self.estop.value)

    def set_state(self, state_name: str) -> None:
        if state_name not in {"idle", "moving", "success", "alarm"}:
            raise MotionError(f"unknown machine state '{state_name}'")
        self._state_name = state_name
        for led in [self.led_idle, self.led_moving, self.led_success, self.alarm_warning]:
            if led is not None:
                led.off()
        if self.alarm_buzzer is not None:
            self.alarm_buzzer.off()

        if state_name == "idle":
            if self.led_idle is not None:
                self.led_idle.on()
        elif state_name == "moving":
            if self.led_moving is not None:
                self.led_moving.on()
        elif state_name == "success":
            if self.led_success is not None:
                self.led_success.on()
        elif state_name == "alarm":
            if self.alarm_warning is not None:
                self.alarm_warning.on()
            if self.alarm_buzzer is not None:
                self.alarm_buzzer.on()

    def status(self) -> dict[str, object]:
        state_name = self._state_name
        if self.emergency_stop_active() or self._stop_requested:
            state_name = "alarm"

        return {
            "estop": bool(self.estop.value),
            "state": state_name,
            "speed_override": self.speed_override,
            "timer_seconds": self.timer_seconds,
            "x": self.x.status(),
            "y": self.y.status(),
            "z": self.z.status(),
            "current_position": self.current_position(),
            "last_plan": self.last_plan.to_dict() if self.last_plan is not None else None,
        }

    def _execute_coordinated_plan(self, plan: CoordinatedMovePlan) -> None:
        master_steps = plan.master_steps
        if master_steps <= 0:
            return

        axes = {name: self.axes()[name] for name in plan.axes}
        directions = {name: axis_plan.direction for name, axis_plan in plan.axes.items()}
        steps = {name: axis_plan.steps for name, axis_plan in plan.axes.items()}

        for axis_name, axis_plan in plan.axes.items():
            delta_steps = axis_plan.steps if axis_plan.direction == axes[axis_name].config.forward_direction else -axis_plan.steps
            axes[axis_name]._guard_before_move(axis_plan.direction, delta_steps)
            axes[axis_name].direction.value = bool(axis_plan.direction)

        # Production NUCLEO protocol v3 owns all STEP generation. Never fall
        # through to Raspberry Pi placeholder GPIO for a coordinated move.
        backends = {id(axis.motion_backend): axis.motion_backend for axis in axes.values() if axis.motion_backend is not None}
        backend = next(iter(backends.values())) if len(backends) == 1 else None
        if backend is not None and getattr(backend, "expected_protocol", 1) >= 3 and hasattr(backend, "move_parallel"):
            backend_plans = {
                axis_name: {
                    "direction": axis_plan.direction,
                    "steps": axis_plan.steps,
                    "speed_hz": max(10.0, axis_plan.steps / max(plan.duration_s, 0.001)),
                }
                for axis_name, axis_plan in plan.axes.items()
                if axis_plan.steps > 0
            }

            def coordinated_stop() -> bool:
                if self.emergency_stop_active() or self.stop_requested() or self.controlled_stop_requested():
                    return True
                return any(
                    (axis_plan.direction == axes[name].config.home_direction and axes[name].head_limit.value)
                    or (axis_plan.direction != axes[name].config.home_direction and axes[name].tail_limit.value)
                    for name, axis_plan in plan.axes.items()
                )

            result = backend.move_parallel(
                backend_plans,
                timeout_s=plan.duration_s + 4.0,
                stop_requested=coordinated_stop,
            )
            completed = dict(result.get("steps", {}))
            for axis_name, axis_plan in plan.axes.items():
                count = int(completed.get(axis_name, axis_plan.steps))
                axes[axis_name].position_steps += count if axis_plan.direction == axes[axis_name].config.forward_direction else -count
            if result.get("stopped"):
                if self.emergency_stop_active():
                    raise EmergencyStopError("emergency stop during coordinated move")
                if self.stop_requested():
                    raise StopRequestedError("stop requested during coordinated move")
                if self.controlled_stop_requested():
                    raise ControlledStopError("coordinated controlled stop completed")
                for axis in axes.values():
                    axis.is_homed = False
                raise LimitTriggeredError("physical limit triggered during coordinated move")
            sleep(max(axis.config.settle_delay for axis in axes.values()))
            return

        accumulators = {name: 0 for name in plan.axes}
        half_periods = _build_half_periods(master_steps, plan.duration_s, ramp_ratio=1.6)
        controlled_remaining: int | None = None
        controlled_total = 0

        try:
            for index, half_period in enumerate(half_periods):
                if index % 5 == 0:
                    for axis_name, axis in axes.items():
                        axis._guard_during_move(directions[axis_name])
                if controlled_remaining is None and self.controlled_stop_requested():
                    controlled_remaining = min(50, master_steps - index)
                    controlled_total = controlled_remaining
                stop_scale = 1.0
                if controlled_remaining is not None:
                    stop_scale = 1.0 + (3.0 * (1.0 - controlled_remaining / max(controlled_total, 1)))
                for axis_name, axis in axes.items():
                    accumulators[axis_name] += steps[axis_name]
                    if accumulators[axis_name] >= master_steps:
                        axis.pulse.on()
                sleep(half_period * stop_scale)
                for axis_name, axis in axes.items():
                    if accumulators[axis_name] >= master_steps:
                        axis.pulse.off()
                        axis.position_steps += 1 if directions[axis_name] == axis.config.forward_direction else -1
                        accumulators[axis_name] -= master_steps
                sleep(half_period * stop_scale)
                if controlled_remaining is not None:
                    controlled_remaining -= 1
                    if controlled_remaining <= 0:
                        for axis in axes.values():
                            axis.stop()
                        raise ControlledStopError("coordinated controlled stop completed")
        except ControlledStopError:
            for axis in axes.values():
                axis.stop()
            raise
        except (EmergencyStopError, StopRequestedError, LimitTriggeredError):
            for axis in axes.values():
                axis.stop()
                axis.is_homed = False
            raise

        sleep(max(axis.config.settle_delay for axis in axes.values()))


def build_default_slots(slot_count: int = 30) -> dict[str, SlotPosition]:
    return {
        str(index): SlotPosition(code=str(index), x_mm=0.0, y_mm=0.0, z_mm=0.0)
        for index in range(1, slot_count + 1)
    }


def _build_half_periods(total_steps: int, duration_s: float, ramp_ratio: float = 1.6) -> list[float]:
    if total_steps <= 0 or duration_s <= 0:
        return []
    if total_steps < 6:
        return [duration_s / (2.0 * total_steps)] * total_steps

    ramp_steps = min(max(total_steps // 6, 1), 250)
    weights: list[float] = []
    for index in range(total_steps):
        if index < ramp_steps:
            blend = 1.0 - (index / ramp_steps)
            weight = 1.0 + (ramp_ratio * blend)
        elif index >= total_steps - ramp_steps:
            blend = (index - (total_steps - ramp_steps)) / ramp_steps
            weight = 1.0 + (ramp_ratio * blend)
        else:
            weight = 1.0
        weights.append(weight)

    scale = duration_s / (2.0 * sum(weights))
    return [max(scale * weight, 0.00002) for weight in weights]


def _axis_config_to_dict(config: AxisConfig) -> dict[str, int | float | str]:
    return {
        "name": config.name,
        "pulse_pin": config.pulse_pin,
        "direction_pin": config.direction_pin,
        "head_limit_pin": config.head_limit_pin,
        "tail_limit_pin": config.tail_limit_pin,
        "home_direction": config.home_direction,
        "forward_direction": config.forward_direction,
        "steps_per_mm": config.steps_per_mm,
        "max_travel_mm": config.max_travel_mm,
        "max_speed_mm_s": config.max_speed_mm_s,
        "default_speed_mm_s": config.default_speed_mm_s,
        "settle_delay": config.settle_delay,
        "jog_step_mm": config.jog_step_mm,
        "acceleration": config.acceleration,
        "deceleration": config.deceleration,
        "lead_screw_pitch_mm": config.lead_screw_pitch_mm,
        "motor_steps_per_rev": config.motor_steps_per_rev,
        "driver_microsteps": config.driver_microsteps,
        "home_position_mm": config.home_position_mm,
        "max_pulse_hz": config.max_pulse_hz,
        "commissioned_max_speed_mm_s": config.commissioned_max_speed_mm_s,
        "homing_search_speed_mm_s": config.homing_search_speed_mm_s,
        "homing_latch_speed_mm_s": config.homing_latch_speed_mm_s,
        "homing_timeout_s": config.homing_timeout_s,
        "drive_type": config.drive_type,
        "nominal_travel_mm": config.nominal_travel_mm,
        "measured_travel_mm": config.measured_travel_mm,
        "travel_safety_margin_mm": config.travel_safety_margin_mm,
        "pulley_pitch_mm": config.pulley_pitch_mm,
        "pulley_teeth": config.pulley_teeth,
        "pulses_per_rev": config.pulses_per_rev,
    }


def _axis_config_from_dict(name: str, payload: dict[str, object]) -> AxisConfig:
    lead_screw_pitch_mm = float(payload.get("lead_screw_pitch_mm", 5.0))
    motor_steps_per_rev = int(payload.get("motor_steps_per_rev", 200))
    driver_microsteps = int(payload.get("driver_microsteps", 10))
    default_steps_per_mm = (motor_steps_per_rev * driver_microsteps) / lead_screw_pitch_mm
    steps_per_mm = float(payload.get("steps_per_mm", default_steps_per_mm))

    pulse_delay = payload.get("pulse_delay")
    if pulse_delay is not None:
        speed = 1.0 / (2.0 * float(pulse_delay) * steps_per_mm)
        default_speed = float(payload.get("default_speed_mm_s", speed))
        max_speed = float(payload.get("max_speed_mm_s", max(speed, 30.0)))
    else:
        default_speed = float(payload.get("default_speed_mm_s", 15.0))
        max_speed = float(payload.get("max_speed_mm_s", 30.0))

    return AxisConfig(
        name=name,
        pulse_pin=int(payload["pulse_pin"]),
        direction_pin=int(payload["direction_pin"]),
        head_limit_pin=int(payload["head_limit_pin"]),
        tail_limit_pin=int(payload["tail_limit_pin"]),
        enable_pin=int(payload["enable_pin"]) if payload.get("enable_pin") is not None else None,
        home_direction=int(payload["home_direction"]),
        forward_direction=int(payload["forward_direction"]),
        steps_per_mm=steps_per_mm,
        max_travel_mm=float(payload["max_travel_mm"]),
        max_speed_mm_s=max_speed,
        default_speed_mm_s=default_speed,
        settle_delay=float(payload.get("settle_delay", 0.05)),
        jog_step_mm=float(payload.get("jog_step_mm", 5.0)),
        acceleration=float(payload.get("acceleration", 80.0)),
        deceleration=float(payload.get("deceleration", 80.0)),
        lead_screw_pitch_mm=lead_screw_pitch_mm,
        motor_steps_per_rev=motor_steps_per_rev,
        driver_microsteps=driver_microsteps,
        home_position_mm=float(payload.get("home_position_mm", 0.0)),
        max_pulse_hz=float(payload.get("max_pulse_hz", 50_000.0)),
        commissioned_max_speed_mm_s=float(payload.get("commissioned_max_speed_mm_s", max_speed)),
        homing_search_speed_mm_s=float(payload.get("homing_search_speed_mm_s", min(default_speed, max_speed))),
        homing_latch_speed_mm_s=float(payload.get("homing_latch_speed_mm_s", min(1.0, default_speed, max_speed))),
        homing_timeout_s=float(payload.get("homing_timeout_s", 120.0)),
        drive_type=str(payload.get("drive_type", "lead_screw")),
        nominal_travel_mm=float(payload["nominal_travel_mm"]) if payload.get("nominal_travel_mm") is not None else None,
        measured_travel_mm=float(payload["measured_travel_mm"]) if payload.get("measured_travel_mm") is not None else None,
        travel_safety_margin_mm=float(payload.get("travel_safety_margin_mm", 5.0)),
        pulley_pitch_mm=float(payload["pulley_pitch_mm"]) if payload.get("pulley_pitch_mm") is not None else None,
        pulley_teeth=int(payload["pulley_teeth"]) if payload.get("pulley_teeth") is not None else None,
    )


def build_default_machine_config() -> MachineConfig:
    base = {
        "max_speed_mm_s": 35.0,
        "default_speed_mm_s": 18.0,
        "lead_screw_pitch_mm": 5.0,
        "motor_steps_per_rev": 200,
        "driver_microsteps": 10,
    }
    return MachineConfig(
        x=AxisConfig(
            name="x",
            pulse_pin=16,
            direction_pin=23,
            head_limit_pin=17,
            tail_limit_pin=27,
            home_direction=0,
            forward_direction=1,
            steps_per_mm=400.0,
            max_travel_mm=220.0,
            jog_step_mm=5.0,
            **base,
        ),
        y=AxisConfig(
            name="y",
            pulse_pin=26,
            direction_pin=24,
            head_limit_pin=22,
            tail_limit_pin=9,
            home_direction=0,
            forward_direction=1,
            steps_per_mm=400.0,
            max_travel_mm=260.0,
            jog_step_mm=5.0,
            **base,
        ),
        z=AxisConfig(
            name="z",
            pulse_pin=18,
            direction_pin=25,
            head_limit_pin=11,
            tail_limit_pin=5,
            home_direction=0,
            forward_direction=1,
            steps_per_mm=400.0,
            max_travel_mm=200.0,
            max_speed_mm_s=20.0,
            default_speed_mm_s=10.0,
            jog_step_mm=2.0,
            lead_screw_pitch_mm=5.0,
            motor_steps_per_rev=200,
            driver_microsteps=10,
        ),
        home_order=("z", "y", "x"),
        slots=build_default_slots(),
        safe_z_mm=10.0,
    )


def load_machine_config(path: str | Path) -> MachineConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    axes = payload["axes"]
    x = _axis_config_from_dict("x", axes["x"])
    y = _axis_config_from_dict("y", axes["y"])
    z = _axis_config_from_dict("z", axes["z"])

    slots = build_default_slots()
    for code, slot in payload.get("slots", {}).items():
        slot_code = str(code)
        slots[slot_code] = SlotPosition(
            code=slot_code,
            x_mm=float(slot["x_mm"]),
            y_mm=float(slot["y_mm"]),
            z_mm=float(slot["z_mm"]),
            product_name=str(slot.get("product_name", "")),
            dispense_delay_ms=int(slot.get("dispense_delay_ms", 0)),
        )

    return MachineConfig(
        x=x,
        y=y,
        z=z,
        home_order=tuple(payload.get("home_order", ["z", "y", "x"])),
        slots=slots,
        safe_z_mm=float(payload.get("safe_z_mm", 10.0)),
    )


def save_machine_config(config: MachineConfig, path: str | Path) -> None:
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = config_path.with_name(f".{config_path.name}.tmp")
    temporary_path.write_text(json.dumps(config.to_dict(), indent=2) + "\n", encoding="utf-8")
    os.replace(temporary_path, config_path)


def load_hardware_config(path: str | Path = "hardware_config.json") -> dict:
    """Compatibility wrapper retained for existing motion consumers."""
    try:
        return load_hardware_payload(path)
    except ValueError as exc:
        raise MotionError(str(exc)) from exc


def build_controller(
    config: MachineConfig,
    hw_config_path: str = "hardware_config.json",
    io_backend: object | None = None,
    motion_backend: object | None = None,
) -> MotionController:
    hw_config = load_hardware_config(hw_config_path)
    motion_placeholder_factory = MockFactory() if motion_backend is not None else None
    di_config = hw_config.get("digital_inputs", {})

    def make_input(pin: int, info: dict[str, object], iriv_name: str | None = None):
        if io_backend is not None and iriv_name is not None:
            return io_backend.input_device(iriv_name)
        pull_up_value = info.get("pull_up", False)
        if pull_up_value is None:
            return DigitalInputDevice(
                pin,
                pull_up=None,
                active_state=bool(info.get("active_high", True)),
            )
        pull_up = bool(pull_up_value)
        expected_active_high = not pull_up
        if "active_high" in info and bool(info["active_high"]) != expected_active_high:
            raise MotionError(
                f"GPIO {pin}: active_high conflicts with pull_up; "
                f"use active_high={str(expected_active_high).lower()} or pull_up=null"
            )
        return DigitalInputDevice(pin, pull_up=pull_up)

    estop_info = di_config.get("estop", {})
    estop_button = make_input(int(estop_info.get("pin", 6)), estop_info, "estop")

    motors_config = hw_config.get("motors", {})

    def get_motor_config(axis_name: str, fallback: AxisConfig) -> AxisConfig:
        motor_info = motors_config.get(axis_name, {})
        head_info = di_config.get(f"lim_{axis_name}_head", di_config.get(f"home_sensor_{axis_name}", {}))
        tail_info = di_config.get(f"lim_{axis_name}_tail", {})
        params = hw_config.get("machine_parameters", {}).get("axes", {}).get(axis_name, {})

        payload = _axis_config_to_dict(fallback)
        payload.update(
            {
                "pulse_pin": int(motor_info.get("step_pin", fallback.pulse_pin)),
                "direction_pin": int(motor_info.get("dir_pin", fallback.direction_pin)),
                "enable_pin": motor_info.get("enable_pin", fallback.enable_pin),
                "head_limit_pin": int(head_info.get("pin", fallback.head_limit_pin)),
                "tail_limit_pin": int(tail_info.get("pin", fallback.tail_limit_pin)),
            }
        )
        payload.update(params)
        return _axis_config_from_dict(axis_name, payload)

    x_config = get_motor_config("x", config.x)
    y_config = get_motor_config("y", config.y)
    z_config = get_motor_config("z", config.z)

    machine_params = hw_config.get("machine_parameters", {})
    config = MachineConfig(
        x=x_config,
        y=y_config,
        z=z_config,
        home_order=tuple(machine_params.get("home_order", config.home_order)),
        slots=config.slots,
        safe_z_mm=float(machine_params.get("safe_z_mm", config.safe_z_mm)),
    )

    controller_ref: dict[str, MotionController] = {}

    def stop_requested() -> bool:
        return controller_ref["controller"].stop_requested()

    def controlled_stop_requested() -> bool:
        return controller_ref["controller"].controlled_stop_requested()

    def make_axis(cfg: AxisConfig) -> AxisController:
        motor_info = motors_config.get(cfg.name, {})
        motor_active_high = bool(motor_info.get("active_high", True))
        enable_active_high = bool(motor_info.get("enable_active_high", motor_active_high))
        placeholder_args = {"pin_factory": motion_placeholder_factory} if motion_placeholder_factory is not None else {}
        pulse_dev = OutputDevice(cfg.pulse_pin, active_high=motor_active_high, initial_value=False, **placeholder_args)
        dir_dev = OutputDevice(cfg.direction_pin, active_high=motor_active_high, initial_value=False, **placeholder_args)
        enable_dev = (
            OutputDevice(cfg.enable_pin, active_high=enable_active_high, initial_value=True, **placeholder_args)
            if cfg.enable_pin is not None
            else None
        )

        head_info = di_config.get(f"lim_{cfg.name}_head", di_config.get(f"home_sensor_{cfg.name}", {}))
        tail_info = di_config.get(f"lim_{cfg.name}_tail", {})
        return AxisController(
            config=cfg,
            pulse=pulse_dev,
            direction=dir_dev,
            head_limit=make_input(cfg.head_limit_pin, head_info, f"{cfg.name}_head_limit"),
            tail_limit=make_input(cfg.tail_limit_pin, tail_info, f"{cfg.name}_tail_limit"),
            estop=estop_button,
            stop_requested=stop_requested,
            controlled_stop_requested=controlled_stop_requested,
            enable=enable_dev,
            motion_backend=motion_backend,
        )

    x_axis = make_axis(config.x)
    y_axis = make_axis(config.y)
    z_axis = make_axis(config.z)

    do_config = hw_config.get("digital_outputs", {})

    iriv_output_names = {
        "led_moving": "moving",
        "led_success": "ready",
        "alarm_warning": "alarm",
        "alarm_buzzer": "alarm",
    }

    def make_output(name: str, default: bool = False):
        if io_backend is not None:
            iriv_name = iriv_output_names.get(name)
            return io_backend.output_device(iriv_name) if iriv_name is not None else None
        info = do_config.get(name, {})
        if "pin" not in info:
            return None
        return OutputDevice(
            int(info["pin"]),
            active_high=bool(info.get("active_high", True)),
            initial_value=bool(info.get("initial_value", default)),
        )

    controller = MotionController(
        x=x_axis,
        y=y_axis,
        z=z_axis,
        estop=estop_button,
        config=config,
        led_idle=make_output("led_idle", True),
        led_moving=make_output("led_moving"),
        led_success=make_output("led_success"),
        alarm_warning=make_output("alarm_warning"),
        alarm_buzzer=make_output("alarm_buzzer"),
    )
    controller_ref["controller"] = controller
    return controller


def build_default_controller() -> MotionController:
    return build_controller(build_default_machine_config())
