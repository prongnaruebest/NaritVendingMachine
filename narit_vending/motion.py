from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from time import sleep

# pyrefly: ignore [missing-import]
from gpiozero import DigitalInputDevice, OutputDevice


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
    pulse_delay: float = 0.001
    settle_delay: float = 0.05
    jog_step_mm: float = 5.0


@dataclass(frozen=True)
class SlotPosition:
    code: str
    x_mm: float
    y_mm: float
    z_mm: float


@dataclass(frozen=True)
class MachineConfig:
    x: AxisConfig
    y: AxisConfig
    z: AxisConfig
    home_order: tuple[str, ...] = ("z", "x", "y")
    slots: dict[str, SlotPosition] = field(default_factory=dict)
    safe_z_mm: float = 10.0

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
                code: {"x_mm": slot.x_mm, "y_mm": slot.y_mm, "z_mm": slot.z_mm}
                for code, slot in sorted(self.slots.items(), key=lambda item: int(item[0]))
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
        stop_requested: callable,
    ) -> None:
        self.config = config
        self.pulse = pulse
        self.direction = direction
        self.head_limit = head_limit
        self.tail_limit = tail_limit
        self.estop = estop
        self.stop_requested = stop_requested
        self.position_steps = 0
        self.is_homed = False

    @property
    def position_mm(self) -> float:
        return self.position_steps / self.config.steps_per_mm

    def mm_to_steps(self, distance_mm: float) -> int:
        return round(distance_mm * self.config.steps_per_mm)

    def move_steps(self, steps: int, direction: int | None = None) -> int:
        if steps < 0:
            raise ValueError("steps must be >= 0")
        if steps == 0:
            return 0

        move_direction = self.config.forward_direction if direction is None else direction
        delta_steps = steps if move_direction == self.config.forward_direction else -steps
        self._guard_before_move(move_direction, delta_steps)
        self.direction.value = bool(move_direction)

        START_DELAY = 0.0015
        PULSE_DELAY_MAX = self.config.pulse_delay
        ACCEL_STEPS = min(150, steps // 2)

        moved = 0
        for i in range(steps):
            if i % 20 == 0:
                self._guard_during_move(move_direction)
            if i < ACCEL_STEPS and START_DELAY > PULSE_DELAY_MAX:
                current_delay = START_DELAY - ((START_DELAY - PULSE_DELAY_MAX) * (i / ACCEL_STEPS))
            else:
                current_delay = PULSE_DELAY_MAX

            self.pulse.on()
            sleep(current_delay)
            self.pulse.off()
            sleep(current_delay)
            moved += 1
            self.position_steps += 1 if move_direction == self.config.forward_direction else -1
        sleep(self.config.settle_delay)
        return moved

    def move_mm(self, distance_mm: float) -> int:
        if distance_mm == 0:
            return 0
        steps = abs(self.mm_to_steps(distance_mm))
        direction = self.config.forward_direction if distance_mm > 0 else self.config.home_direction
        return self.move_steps(steps, direction=direction)

    def move_to_mm(self, target_mm: float) -> int:
        if not self.is_homed:
            raise NotHomedError(f"{self.config.name}: axis must be homed before move_to_mm")
        if target_mm < 0 or target_mm > self.config.max_travel_mm:
            raise MotionError(
                f"{self.config.name}: target {target_mm:.2f} mm outside 0-{self.config.max_travel_mm:.2f} mm"
            )
        return self.move_mm(target_mm - self.position_mm)

    def home(self, backoff_steps: int = 20, max_steps: int = 20000) -> int:
        if self.estop.value:
            raise EmergencyStopError(f"{self.config.name}: emergency stop is active")

        homing_delay = max(0.0008, self.config.pulse_delay)
        self.direction.value = bool(self.config.home_direction)
        moved = 0
        limit_active = self.head_limit.value
        while not limit_active:
            if moved >= max_steps:
                raise LimitTriggeredError(f"{self.config.name}: home not reached within {max_steps} steps")
            if moved % 20 == 0:
                self._guard_during_move(self.config.home_direction)
                limit_active = self.head_limit.value
            self.pulse.on()
            sleep(homing_delay)
            self.pulse.off()
            sleep(homing_delay)
            moved += 1

        sleep(self.config.settle_delay)

        if backoff_steps > 0:
            release_direction = 1 - self.config.home_direction
            self.direction.value = bool(release_direction)
            released = 0
            limit_active = self.head_limit.value
            while limit_active and released < backoff_steps:
                if released % 20 == 0:
                    self._guard_during_move(release_direction)
                    limit_active = self.head_limit.value
                self.pulse.on()
                sleep(homing_delay)
                self.pulse.off()
                sleep(homing_delay)
                released += 1
            sleep(self.config.settle_delay)

        self.position_steps = 0
        self.is_homed = True
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
            raise EmergencyStopError(f"{self.config.name}: emergency stop triggered")
        if self.stop_requested():
            self.stop()
            raise StopRequestedError(f"{self.config.name}: stop requested")
        if direction == self.config.home_direction and self.head_limit.value:
            self.stop()
            raise LimitTriggeredError(f"{self.config.name}: head limit triggered")
        if direction != self.config.home_direction and self.tail_limit.value:
            self.stop()
            raise LimitTriggeredError(f"{self.config.name}: tail limit triggered")


class MotionController:
    def __init__(self, x: AxisController, y: AxisController, z: AxisController, estop: DigitalInputDevice, config: MachineConfig) -> None:
        self.x = x
        self.y = y
        self.z = z
        self.estop = estop
        self.config = config
        self._stop_requested = False

    def axes(self) -> dict[str, AxisController]:
        return {"x": self.x, "y": self.y, "z": self.z}

    def home_axis(self, axis_name: str) -> None:
        self.clear_stop()
        self.axes()[axis_name.lower()].home()

    def home_all(self) -> None:
        self.clear_stop()
        for axis_name in self.config.home_order:
            self.home_axis(axis_name)

    def move_by_mm(self, x_mm: float = 0, y_mm: float = 0, z_mm: float = 0) -> None:
        self.clear_stop()
        if x_mm:
            self.x.move_mm(x_mm)
        if y_mm:
            self.y.move_mm(y_mm)
        if z_mm:
            self.z.move_mm(z_mm)

    def move_to(self, x_mm: float | None = None, y_mm: float | None = None, z_mm: float | None = None) -> None:
        self.clear_stop()
        if x_mm is not None:
            self.x.move_to_mm(x_mm)
        if y_mm is not None:
            self.y.move_to_mm(y_mm)
        if z_mm is not None:
            self.z.move_to_mm(z_mm)

    def current_position(self) -> dict[str, float]:
        return {
            "x_mm": round(self.x.position_mm, 3),
            "y_mm": round(self.y.position_mm, 3),
            "z_mm": round(self.z.position_mm, 3),
        }

    def move_to_slot(self, slot_code: str) -> SlotPosition:
        self.clear_stop()
        slot = self.config.slots.get(str(slot_code))
        if slot is None:
            raise MotionError(f"unknown slot '{slot_code}'")

        safe_z = min(self.config.safe_z_mm, self.z.config.max_travel_mm)
        if self.z.is_homed and self.z.position_mm < safe_z:
            self.z.move_to_mm(safe_z)

        self.move_to(x_mm=slot.x_mm, y_mm=slot.y_mm)
        self.z.move_to_mm(slot.z_mm)
        return slot

    def update_slot(self, slot_code: str, x_mm: float, y_mm: float, z_mm: float) -> None:
        code = str(slot_code)
        if code not in self.config.slots:
            raise MotionError(f"unknown slot '{slot_code}'")
        new_slots = dict(self.config.slots)
        new_slots[code] = SlotPosition(code=code, x_mm=x_mm, y_mm=y_mm, z_mm=z_mm)
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

    def status(self) -> dict[str, object]:
        return {
            "estop": bool(self.estop.value),
            "x": self.x.status(),
            "y": self.y.status(),
            "z": self.z.status(),
            "current_position": self.current_position(),
        }


def build_default_slots(slot_count: int = 30) -> dict[str, SlotPosition]:
    return {
        str(index): SlotPosition(code=str(index), x_mm=0.0, y_mm=0.0, z_mm=0.0)
        for index in range(1, slot_count + 1)
    }


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
        "pulse_delay": config.pulse_delay,
        "settle_delay": config.settle_delay,
        "jog_step_mm": config.jog_step_mm,
    }


def _axis_config_from_dict(name: str, payload: dict[str, object]) -> AxisConfig:
    return AxisConfig(
        name=name,
        pulse_pin=int(payload["pulse_pin"]),
        direction_pin=int(payload["direction_pin"]),
        head_limit_pin=int(payload["head_limit_pin"]),
        tail_limit_pin=int(payload["tail_limit_pin"]),
        home_direction=int(payload["home_direction"]),
        forward_direction=int(payload["forward_direction"]),
        steps_per_mm=float(payload["steps_per_mm"]),
        max_travel_mm=float(payload["max_travel_mm"]),
        pulse_delay=float(payload.get("pulse_delay", 0.001)),
        settle_delay=float(payload.get("settle_delay", 0.05)),
        jog_step_mm=float(payload.get("jog_step_mm", 5.0)),
    )


def build_default_machine_config(pulse_delay: float = 0.001) -> MachineConfig:
    return MachineConfig(
        x=AxisConfig(
            name="x",
            pulse_pin=16,
            direction_pin=23,
            head_limit_pin=17,
            tail_limit_pin=27,
            home_direction=0,
            forward_direction=1,
            steps_per_mm=80.0,
            max_travel_mm=220.0,
            pulse_delay=pulse_delay,
            jog_step_mm=5.0,
        ),
        y=AxisConfig(
            name="y",
            pulse_pin=26,
            direction_pin=24,
            head_limit_pin=22,
            tail_limit_pin=9,
            home_direction=0,
            forward_direction=1,
            steps_per_mm=80.0,
            max_travel_mm=260.0,
            pulse_delay=pulse_delay,
            jog_step_mm=5.0,
        ),
        z=AxisConfig(
            name="z",
            pulse_pin=18,
            direction_pin=25,
            head_limit_pin=11,
            tail_limit_pin=5,
            home_direction=0,
            forward_direction=1,
            steps_per_mm=50.0,
            max_travel_mm=200.0,
            pulse_delay=pulse_delay,
            jog_step_mm=2.0,
        ),
        home_order=("z", "x", "y"),
        slots=build_default_slots(),
        safe_z_mm=10.0,
    )


def load_machine_config(path: str | Path, pulse_delay: float | None = None) -> MachineConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    axes = payload["axes"]
    x = _axis_config_from_dict("x", axes["x"])
    y = _axis_config_from_dict("y", axes["y"])
    z = _axis_config_from_dict("z", axes["z"])

    if pulse_delay is not None:
        x = AxisConfig(**{**x.__dict__, "pulse_delay": pulse_delay})
        y = AxisConfig(**{**y.__dict__, "pulse_delay": pulse_delay})
        z = AxisConfig(**{**z.__dict__, "pulse_delay": pulse_delay})

    slots = build_default_slots()
    for code, slot in payload.get("slots", {}).items():
        slot_code = str(code)
        slots[slot_code] = SlotPosition(
            code=slot_code,
            x_mm=float(slot["x_mm"]),
            y_mm=float(slot["y_mm"]),
            z_mm=float(slot["z_mm"]),
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
    Path(path).write_text(json.dumps(config.to_dict(), indent=2) + "\n", encoding="utf-8")


def build_controller(config: MachineConfig) -> MotionController:
    estop_button = DigitalInputDevice(6, pull_up=False)
    controller_ref: dict[str, MotionController] = {}
    stop_requested = lambda: controller_ref["controller"].stop_requested()

    x_axis = AxisController(
        config=config.x,
        pulse=OutputDevice(config.x.pulse_pin, active_high=True, initial_value=False),
        direction=OutputDevice(config.x.direction_pin, active_high=True, initial_value=False),
        head_limit=DigitalInputDevice(config.x.head_limit_pin, pull_up=False),
        tail_limit=DigitalInputDevice(config.x.tail_limit_pin, pull_up=False),
        estop=estop_button,
        stop_requested=stop_requested,
    )
    y_axis = AxisController(
        config=config.y,
        pulse=OutputDevice(config.y.pulse_pin, active_high=True, initial_value=False),
        direction=OutputDevice(config.y.direction_pin, active_high=True, initial_value=False),
        head_limit=DigitalInputDevice(config.y.head_limit_pin, pull_up=False),
        tail_limit=DigitalInputDevice(config.y.tail_limit_pin, pull_up=False),
        estop=estop_button,
        stop_requested=stop_requested,
    )
    z_axis = AxisController(
        config=config.z,
        pulse=OutputDevice(config.z.pulse_pin, active_high=True, initial_value=False),
        direction=OutputDevice(config.z.direction_pin, active_high=True, initial_value=False),
        head_limit=DigitalInputDevice(config.z.head_limit_pin, pull_up=False),
        tail_limit=DigitalInputDevice(config.z.tail_limit_pin, pull_up=False),
        estop=estop_button,
        stop_requested=stop_requested,
    )
    controller = MotionController(x=x_axis, y=y_axis, z=z_axis, estop=estop_button, config=config)
    controller_ref["controller"] = controller
    return controller


def build_default_controller(pulse_delay: float = 0.001) -> MotionController:
    return build_controller(build_default_machine_config(pulse_delay=pulse_delay))
