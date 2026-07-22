from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from time import sleep
from typing import Callable

if os.name != "posix" and "GPIOZERO_PIN_FACTORY" not in os.environ:
    os.environ["GPIOZERO_PIN_FACTORY"] = "mock"

from gpiozero import DigitalInputDevice, OutputDevice


_logger = logging.getLogger(__name__)


def _slot_sort_key(item: tuple[str, object]) -> tuple[int, int | str]:
    code = str(item[0])
    return (0, int(code)) if code.isdigit() else (1, code)


class MotionError(RuntimeError):
    pass


class LimitTriggeredError(MotionError):
    pass


class EmergencyStopError(MotionError):
    pass


class NotHomedError(MotionError):
    pass


class StopRequestedError(MotionError):
    pass


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

    def __post_init__(self) -> None:
        positive_values = {
            "steps_per_mm": self.steps_per_mm,
            "max_travel_mm": self.max_travel_mm,
            "max_speed_mm_s": self.max_speed_mm_s,
            "default_speed_mm_s": self.default_speed_mm_s,
            "lead_screw_pitch_mm": self.lead_screw_pitch_mm,
            "motor_steps_per_rev": self.motor_steps_per_rev,
            "driver_microsteps": self.driver_microsteps,
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

    @property
    def step_pin(self) -> int:
        return self.pulse_pin

    @property
    def dir_pin(self) -> int:
        return self.direction_pin

    @property
    def pulses_per_rev(self) -> int:
        return self.motor_steps_per_rev * self.driver_microsteps


@dataclass(frozen=True)
class SlotPosition:
    code: str
    x_mm: float
    y_mm: float
    z_mm: float
    product_name: str = ""
    dispense_delay_ms: int = 0


@dataclass(frozen=True)
class AxisMovePlan:
    axis: str
    current_mm: float
    target_mm: float
    distance_mm: float
    direction: int
    steps: int
    speed_mm_s: float
    duration_s: float

    @property
    def pulse_hz(self) -> float:
        if self.duration_s <= 0:
            return 0.0
        return self.steps / self.duration_s

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "axis": self.axis,
            "current_mm": round(self.current_mm, 3),
            "target_mm": round(self.target_mm, 3),
            "distance_mm": round(self.distance_mm, 3),
            "direction": self.direction,
            "steps": self.steps,
            "speed_mm_s": round(self.speed_mm_s, 3),
            "duration_s": round(self.duration_s, 3),
            "pulse_hz": round(self.pulse_hz, 3),
        }


@dataclass(frozen=True)
class CoordinatedMovePlan:
    axes: dict[str, AxisMovePlan]
    duration_s: float
    mode: str

    @property
    def total_distance_mm(self) -> float:
        return max((abs(plan.distance_mm) for plan in self.axes.values()), default=0.0)

    @property
    def master_steps(self) -> int:
        return max((plan.steps for plan in self.axes.values()), default=0)

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "duration_s": round(self.duration_s, 3),
            "master_steps": self.master_steps,
            "total_distance_mm": round(self.total_distance_mm, 3),
            "axes": {name: plan.to_dict() for name, plan in self.axes.items()},
        }


@dataclass(frozen=True)
class MachineConfig:
    x: AxisConfig
    y: AxisConfig
    z: AxisConfig
    home_order: tuple[str, ...] = ("z", "x", "y")
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
        enable: OutputDevice | None = None,
    ) -> None:
        self.config = config
        self.pulse = pulse
        self.direction = direction
        self.head_limit = head_limit
        self.tail_limit = tail_limit
        self.estop = estop
        self.stop_requested = stop_requested
        self.enable = enable
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
        return min(requested, self.config.max_speed_mm_s)

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
            raise MotionError(
                f"{self.config.name}: target {target_mm:.2f} mm outside 0-{self.config.max_travel_mm:.2f} mm"
            )
        return self.plan_relative_move(target_mm - self.position_mm, speed_mm_s=speed_mm_s, time_s=time_s)

    def move_mm(self, distance_mm: float, speed_mm_s: float | None = None, time_s: float | None = None) -> int:
        plan = self.plan_relative_move(distance_mm, speed_mm_s=speed_mm_s, time_s=time_s)
        return self._execute_plan(plan)

    def move_to_mm(self, target_mm: float, speed_mm_s: float | None = None, time_s: float | None = None) -> int:
        plan = self.plan_absolute_move(target_mm, speed_mm_s=speed_mm_s, time_s=time_s)
        return self._execute_plan(plan)

    def home(self, backoff_steps: int = 20, max_steps: int = 200000) -> int:
        _logger.info("Home %s: starting", self.config.name)
        if self.estop.value:
            raise EmergencyStopError(f"{self.config.name}: emergency stop is active")

        homing_speed = min(8.0, self.config.max_speed_mm_s)
        duration_s = max_steps / max(homing_speed * self.config.steps_per_mm, 1.0)
        half_periods = _build_half_periods(max_steps, duration_s, ramp_ratio=0.8)
        self.direction.value = bool(self.config.home_direction)
        moved = 0
        limit_active = self.head_limit.value

        while not limit_active:
            if moved >= max_steps:
                raise LimitTriggeredError(f"{self.config.name}: home not reached within {max_steps} steps")
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

        if backoff_steps > 0:
            release_direction = 1 - self.config.home_direction
            self.direction.value = bool(release_direction)
            released = 0
            while self.head_limit.value and released < backoff_steps:
                if released % 10 == 0:
                    self._guard_during_move(release_direction)
                self._pulse_once(half_periods[min(released, len(half_periods) - 1)])
                released += 1
            sleep(self.config.settle_delay)
            if self.head_limit.value:
                raise LimitTriggeredError(
                    f"{self.config.name}: home sensor did not release after {backoff_steps} backoff steps"
                )

        self.position_steps = 0
        self.is_homed = True
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
            if required_speed > self.config.max_speed_mm_s:
                raise MotionError(
                    f"{self.config.name}: requested {required_speed:.2f} mm/s exceeds limit {self.config.max_speed_mm_s:.2f} mm/s"
                )
            return duration_s

        clamped_speed = self.clamp_speed(speed_mm_s)
        return distance_mm / clamped_speed

    def _execute_plan(self, plan: AxisMovePlan) -> int:
        if plan.steps == 0:
            return 0

        self.direction.value = bool(plan.direction)
        half_periods = _build_half_periods(plan.steps, plan.duration_s, ramp_ratio=1.6)
        moved = 0
        for index, half_period in enumerate(half_periods):
            if index % 5 == 0:
                self._guard_during_move(plan.direction)
            self._pulse_once(half_period)
            self.position_steps += 1 if plan.direction == self.config.forward_direction else -1
            moved += 1
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
            raise LimitTriggeredError(f"{self.config.name}: head limit already active")
        if direction != self.config.home_direction and self.tail_limit.value:
            raise LimitTriggeredError(f"{self.config.name}: tail limit already active")
        if self.is_homed:
            target_steps = self.position_steps + delta_steps
            max_steps = self.mm_to_steps(self.config.max_travel_mm)
            if target_steps < 0 or target_steps > max_steps:
                raise MotionError(
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
            self.is_homed = False
            raise LimitTriggeredError(f"{self.config.name}: head limit triggered")
        if direction != self.config.home_direction and self.tail_limit.value:
            self.stop()
            self.is_homed = False
            raise LimitTriggeredError(f"{self.config.name}: tail limit triggered")


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
        if progress is not None:
            progress(axis.config.name, "homing")
        axis.home()
        if progress is not None:
            progress(axis.config.name, "passed")

    def home_all(self, progress: Callable[[str, str], None] | None = None) -> None:
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
            if required_speed > axis.config.max_speed_mm_s:
                raise MotionError(
                    f"{axis_name}: requested {required_speed:.2f} mm/s exceeds limit {axis.config.max_speed_mm_s:.2f} mm/s"
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

    def clear_stop(self) -> None:
        self._stop_requested = False

    def stop_requested(self) -> bool:
        return self._stop_requested

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

        accumulators = {name: 0 for name in plan.axes}
        half_periods = _build_half_periods(master_steps, plan.duration_s, ramp_ratio=1.6)

        try:
            for index, half_period in enumerate(half_periods):
                if index % 5 == 0:
                    for axis_name, axis in axes.items():
                        axis._guard_during_move(directions[axis_name])
                for axis_name, axis in axes.items():
                    accumulators[axis_name] += steps[axis_name]
                    if accumulators[axis_name] >= master_steps:
                        axis.pulse.on()
                sleep(half_period)
                for axis_name, axis in axes.items():
                    if accumulators[axis_name] >= master_steps:
                        axis.pulse.off()
                        axis.position_steps += 1 if directions[axis_name] == axis.config.forward_direction else -1
                        accumulators[axis_name] -= master_steps
                sleep(half_period)
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
        home_order=("z", "x", "y"),
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
        home_order=tuple(payload.get("home_order", ["z", "x", "y"])),
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
    p = Path(path)
    if not p.exists():
        p = Path(__file__).parent.parent / "hardware_config.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            raise MotionError(f"Failed to parse hardware config '{p}': {exc}") from exc
    return {}


def build_controller(config: MachineConfig, hw_config_path: str = "hardware_config.json") -> MotionController:
    hw_config = load_hardware_config(hw_config_path)
    di_config = hw_config.get("digital_inputs", {})

    def make_input(pin: int, info: dict[str, object]) -> DigitalInputDevice:
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
    estop_button = make_input(int(estop_info.get("pin", 6)), estop_info)

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

    def make_axis(cfg: AxisConfig) -> AxisController:
        motor_info = motors_config.get(cfg.name, {})
        motor_active_high = bool(motor_info.get("active_high", True))
        pulse_dev = OutputDevice(cfg.pulse_pin, active_high=motor_active_high, initial_value=False)
        dir_dev = OutputDevice(cfg.direction_pin, active_high=motor_active_high, initial_value=False)
        enable_dev = (
            OutputDevice(cfg.enable_pin, active_high=motor_active_high, initial_value=True)
            if cfg.enable_pin is not None
            else None
        )

        head_info = di_config.get(f"lim_{cfg.name}_head", di_config.get(f"home_sensor_{cfg.name}", {}))
        tail_info = di_config.get(f"lim_{cfg.name}_tail", {})
        return AxisController(
            config=cfg,
            pulse=pulse_dev,
            direction=dir_dev,
            head_limit=make_input(cfg.head_limit_pin, head_info),
            tail_limit=make_input(cfg.tail_limit_pin, tail_info),
            estop=estop_button,
            stop_requested=stop_requested,
            enable=enable_dev,
        )

    x_axis = make_axis(config.x)
    y_axis = make_axis(config.y)
    z_axis = make_axis(config.z)

    do_config = hw_config.get("digital_outputs", {})

    def make_output(name: str, default: bool = False) -> OutputDevice | None:
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
