from __future__ import annotations

import os
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from time import sleep
from typing import Callable

# Set GPIOZero mock factory if not running on Raspberry Pi to prevent errors on Windows/macOS.
if os.name != "posix" and "GPIOZERO_PIN_FACTORY" not in os.environ:
    os.environ["GPIOZERO_PIN_FACTORY"] = "mock"

# pyrefly: ignore [missing-import]
from gpiozero import DigitalInputDevice, OutputDevice


_logger = logging.getLogger(__name__)


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
    max_speed_mm_s: float = 50.0
    default_speed_mm_s: float = 20.0
    settle_delay: float = 0.05
    jog_step_mm: float = 5.0
    enable_pin: int | None = None
    acceleration: float = 100.0
    deceleration: float = 100.0

    @property
    def step_pin(self) -> int:
        return self.pulse_pin

    @property
    def dir_pin(self) -> int:
        return self.direction_pin


@dataclass(frozen=True)
class SlotPosition:
    code: str
    x_mm: float
    y_mm: float
    z_mm: float
    product_name: str = ""
    dispense_delay_ms: int = 0


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
                code: {
                    "x_mm": slot.x_mm, "y_mm": slot.y_mm, "z_mm": slot.z_mm,
                    "product_name": slot.product_name,
                    "dispense_delay_ms": slot.dispense_delay_ms,
                }
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

    @property
    def position_mm(self) -> float:
        return self.position_steps / self.config.steps_per_mm

    def mm_to_steps(self, distance_mm: float) -> int:
        return round(distance_mm * self.config.steps_per_mm)

    def move_steps(self, steps: int, direction: int | None = None, speed_mm_s: float | None = None) -> int:
        if steps < 0:
            raise ValueError("steps must be >= 0")
        if steps == 0:
            return 0

        move_direction = self.config.forward_direction if direction is None else direction
        delta_steps = steps if move_direction == self.config.forward_direction else -steps
        self._guard_before_move(move_direction, delta_steps)
        self.direction.value = bool(move_direction)

        speed = speed_mm_s if speed_mm_s is not None else self.config.default_speed_mm_s
        speed = max(0.1, min(speed, self.config.max_speed_mm_s))
        
        target_pulse_delay = 1.0 / (2.0 * speed * self.config.steps_per_mm)
        START_DELAY = max(0.0015, target_pulse_delay)
        ACCEL_STEPS = min(150, steps // 2)

        moved = 0
        for i in range(steps):
            if i % 5 == 0:
                self._guard_during_move(move_direction)
            if i < ACCEL_STEPS and START_DELAY > target_pulse_delay:
                current_delay = START_DELAY - ((START_DELAY - target_pulse_delay) * (i / ACCEL_STEPS))
            else:
                current_delay = target_pulse_delay

            self.pulse.on()
            sleep(current_delay)
            self.pulse.off()
            sleep(current_delay)
            moved += 1
            self.position_steps += 1 if move_direction == self.config.forward_direction else -1
        sleep(self.config.settle_delay)
        return moved

    def move_mm(self, distance_mm: float, speed_mm_s: float | None = None) -> int:
        if distance_mm == 0:
            return 0
        steps = abs(self.mm_to_steps(distance_mm))
        direction = self.config.forward_direction if distance_mm > 0 else self.config.home_direction
        return self.move_steps(steps, direction=direction, speed_mm_s=speed_mm_s)

    def move_to_mm(self, target_mm: float, speed_mm_s: float | None = None) -> int:
        if not self.is_homed:
            raise NotHomedError(f"{self.config.name}: axis must be homed before move_to_mm")
        if target_mm < 0 or target_mm > self.config.max_travel_mm:
            raise MotionError(
                f"{self.config.name}: target {target_mm:.2f} mm outside 0-{self.config.max_travel_mm:.2f} mm"
            )
        return self.move_mm(target_mm - self.position_mm, speed_mm_s=speed_mm_s)

    def home(self, backoff_steps: int = 20, max_steps: int = 20000) -> int:
        _logger.info("Home %s: starting", self.config.name)
        if self.estop.value:
            raise EmergencyStopError(f"{self.config.name}: emergency stop is active")

        homing_speed = min(10.0, self.config.max_speed_mm_s)
        homing_delay = 1.0 / (2.0 * homing_speed * self.config.steps_per_mm)
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
        self.set_state("idle")

    def axes(self) -> dict[str, AxisController]:
        return {"x": self.x, "y": self.y, "z": self.z}

    def home_axis(self, axis_name: str, progress: Callable[[str, str], None] | None = None) -> None:
        self.clear_stop()
        name = axis_name.lower()
        if progress is not None:
            progress(name, "homing")
        self.axes()[name].home()
        if progress is not None:
            progress(name, "passed")

    def home_all(self, progress: Callable[[str, str], None] | None = None) -> None:
        self.clear_stop()
        for axis_name in self.config.home_order:
            self.home_axis(axis_name, progress=progress)

    def move_by_mm(self, x_mm: float = 0, y_mm: float = 0, z_mm: float = 0, speed_mm_s: float | None = None) -> None:
        self.clear_stop()
        effective_speed = speed_mm_s or self.speed_override
        if x_mm:
            self.x.move_mm(x_mm, speed_mm_s=effective_speed)
        if y_mm:
            self.y.move_mm(y_mm, speed_mm_s=effective_speed)
        if z_mm:
            self.z.move_mm(z_mm, speed_mm_s=effective_speed)

    def move_to(self, x_mm: float | None = None, y_mm: float | None = None, z_mm: float | None = None, speed_mm_s: float | None = None) -> None:
        self.clear_stop()
        effective_speed = speed_mm_s or self.speed_override
        if x_mm is not None:
            self.x.move_to_mm(x_mm, speed_mm_s=effective_speed)
        if y_mm is not None:
            self.y.move_to_mm(y_mm, speed_mm_s=effective_speed)
        if z_mm is not None:
            self.z.move_to_mm(z_mm, speed_mm_s=effective_speed)

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
            self.z.move_to_mm(safe_z, speed_mm_s=self.speed_override)

        self.move_to(x_mm=slot.x_mm, y_mm=slot.y_mm, speed_mm_s=self.speed_override)
        self.z.move_to_mm(slot.z_mm, speed_mm_s=self.speed_override)
        return slot

    def update_slot(self, slot_code: str, x_mm: float, y_mm: float, z_mm: float,
                     product_name: str | None = None, dispense_delay_ms: int | None = None) -> None:
        code = str(slot_code)
        if code not in self.config.slots:
            raise MotionError(f"unknown slot '{slot_code}'")
        existing = self.config.slots[code]
        new_slots = dict(self.config.slots)
        new_slots[code] = SlotPosition(
            code=code, x_mm=x_mm, y_mm=y_mm, z_mm=z_mm,
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
        state_name = "idle"
        if self.emergency_stop_active():
            state_name = "alarm"
        elif self._stop_requested:
            state_name = "alarm"
        elif self.alarm_warning and self.alarm_warning.value:
            state_name = "alarm"
        elif self.led_moving and self.led_moving.value:
            state_name = "moving"
        elif self.led_success and self.led_success.value:
            state_name = "success"
        elif self.led_idle and self.led_idle.value:
            state_name = "idle"

        return {
            "estop": bool(self.estop.value),
            "state": state_name,
            "speed_override": self.speed_override,
            "timer_seconds": self.timer_seconds,
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
        "max_speed_mm_s": config.max_speed_mm_s,
        "default_speed_mm_s": config.default_speed_mm_s,
        "settle_delay": config.settle_delay,
        "jog_step_mm": config.jog_step_mm,
    }


def _axis_config_from_dict(name: str, payload: dict[str, object]) -> AxisConfig:
    pulse_delay = payload.get("pulse_delay")
    steps = float(payload.get("steps_per_mm", 400.0))
    if pulse_delay is not None:
        # Convert legacy pulse_delay to speed
        speed = 1.0 / (2.0 * float(pulse_delay) * steps)
        default_speed = float(payload.get("default_speed_mm_s", speed))
        max_speed = float(payload.get("max_speed_mm_s", max(speed, 50.0)))
    else:
        default_speed = float(payload.get("default_speed_mm_s", 20.0))
        max_speed = float(payload.get("max_speed_mm_s", 50.0))

    return AxisConfig(
        name=name,
        pulse_pin=int(payload["pulse_pin"]),
        direction_pin=int(payload["direction_pin"]),
        head_limit_pin=int(payload["head_limit_pin"]),
        tail_limit_pin=int(payload["tail_limit_pin"]),
        home_direction=int(payload["home_direction"]),
        forward_direction=int(payload["forward_direction"]),
        steps_per_mm=steps,
        max_travel_mm=float(payload["max_travel_mm"]),
        max_speed_mm_s=max_speed,
        default_speed_mm_s=default_speed,
        settle_delay=float(payload.get("settle_delay", 0.05)),
        jog_step_mm=float(payload.get("jog_step_mm", 5.0)),
    )


def build_default_machine_config() -> MachineConfig:
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
            max_speed_mm_s=50.0,
            default_speed_mm_s=20.0,
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
            steps_per_mm=400.0,
            max_travel_mm=260.0,
            max_speed_mm_s=50.0,
            default_speed_mm_s=20.0,
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
            steps_per_mm=400.0,
            max_travel_mm=200.0,
            max_speed_mm_s=30.0,
            default_speed_mm_s=15.0,
            jog_step_mm=2.0,
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
    Path(path).write_text(json.dumps(config.to_dict(), indent=2) + "\n", encoding="utf-8")


def load_hardware_config(path: str | Path = "hardware_config.json") -> dict:
    p = Path(path)
    if not p.exists():
        p = Path(__file__).parent.parent / "hardware_config.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            _logger.error("Failed to parse hardware config: %s", e)
    return {}


def build_controller(config: MachineConfig, hw_config_path: str = "hardware_config.json") -> MotionController:
    hw_config = load_hardware_config(hw_config_path)

    di_config = hw_config.get("digital_inputs", {})
    estop_info = di_config.get("estop", {})
    estop_pin = int(estop_info.get("pin", 6))
    estop_pull = bool(estop_info.get("pull_up", False))
    estop_button = DigitalInputDevice(estop_pin, pull_up=estop_pull)

    motors_config = hw_config.get("motors", {})
    
    def get_motor_config(axis_name: str, fallback: AxisConfig) -> AxisConfig:
        m = motors_config.get(axis_name, {})
        step_pin = int(m.get("step_pin", m.get("pulse_pin", fallback.pulse_pin)))
        dir_pin = int(m.get("dir_pin", m.get("direction_pin", fallback.direction_pin)))
        enable_pin = m.get("enable_pin")
        enable_pin = int(enable_pin) if enable_pin is not None else fallback.enable_pin

        head_info = di_config.get(f"lim_{axis_name}_head", di_config.get(f"home_sensor_{axis_name}", {}))
        head_pin = int(head_info.get("pin", fallback.head_limit_pin))
        
        tail_info = di_config.get(f"lim_{axis_name}_tail", {})
        tail_pin = int(tail_info.get("pin", fallback.tail_limit_pin))

        params = hw_config.get("machine_parameters", {}).get("axes", {}).get(axis_name, {})

        return AxisConfig(
            name=axis_name,
            pulse_pin=step_pin,
            direction_pin=dir_pin,
            head_limit_pin=head_pin,
            tail_limit_pin=tail_pin,
            enable_pin=enable_pin,
            home_direction=int(params.get("home_direction", fallback.home_direction)),
            forward_direction=int(params.get("forward_direction", fallback.forward_direction)),
            steps_per_mm=float(params.get("steps_per_mm", fallback.steps_per_mm)),
            max_travel_mm=float(params.get("max_travel_mm", fallback.max_travel_mm)),
            max_speed_mm_s=float(params.get("max_speed_mm_s", fallback.max_speed_mm_s)),
            default_speed_mm_s=float(params.get("default_speed_mm_s", fallback.default_speed_mm_s)),
            acceleration=float(params.get("acceleration", fallback.acceleration)),
            deceleration=float(params.get("deceleration", fallback.deceleration)),
            settle_delay=float(params.get("settle_delay", fallback.settle_delay)),
            jog_step_mm=float(params.get("jog_step_mm", fallback.jog_step_mm)),
        )

    x_config = get_motor_config("x", config.x)
    y_config = get_motor_config("y", config.y)
    z_config = get_motor_config("z", config.z)

    params = hw_config.get("machine_parameters", {})
    config = MachineConfig(
        x=x_config,
        y=y_config,
        z=z_config,
        home_order=tuple(params.get("home_order", config.home_order)),
        slots=config.slots,
        safe_z_mm=float(params.get("safe_z_mm", config.safe_z_mm)),
    )

    controller_ref: dict[str, MotionController] = {}
    stop_requested = lambda: controller_ref["controller"].stop_requested()

    def make_axis(cfg: AxisConfig) -> AxisController:
        pulse_dev = OutputDevice(cfg.pulse_pin, active_high=True, initial_value=False)
        dir_dev = OutputDevice(cfg.direction_pin, active_high=True, initial_value=False)
        enable_dev = OutputDevice(cfg.enable_pin, active_high=True, initial_value=False) if cfg.enable_pin is not None else None
        
        head_pull = di_config.get(f"lim_{cfg.name}_head", di_config.get(f"home_sensor_{cfg.name}", {})).get("pull_up", False)
        tail_pull = di_config.get(f"lim_{cfg.name}_tail", {}).get("pull_up", False)

        head_dev = DigitalInputDevice(cfg.head_limit_pin, pull_up=head_pull)
        tail_dev = DigitalInputDevice(cfg.tail_limit_pin, pull_up=tail_pull)

        return AxisController(
            config=cfg,
            pulse=pulse_dev,
            direction=dir_dev,
            head_limit=head_dev,
            tail_limit=tail_dev,
            estop=estop_button,
            stop_requested=stop_requested,
            enable=enable_dev,
        )

    x_axis = make_axis(config.x)
    y_axis = make_axis(config.y)
    z_axis = make_axis(config.z)

    do_config = hw_config.get("digital_outputs", {})
    led_idle_info = do_config.get("led_idle", {})
    led_moving_info = do_config.get("led_moving", {})
    led_success_info = do_config.get("led_success", {})
    alarm_warning_info = do_config.get("alarm_warning", do_config.get("led_alarm", {}))
    alarm_buzzer_info = do_config.get("alarm_buzzer", {})

    led_idle = OutputDevice(int(led_idle_info["pin"]), active_high=led_idle_info.get("active_high", True), initial_value=True) if "pin" in led_idle_info else None
    led_moving = OutputDevice(int(led_moving_info["pin"]), active_high=led_moving_info.get("active_high", True), initial_value=False) if "pin" in led_moving_info else None
    led_success = OutputDevice(int(led_success_info["pin"]), active_high=led_success_info.get("active_high", True), initial_value=False) if "pin" in led_success_info else None
    alarm_warning = OutputDevice(int(alarm_warning_info["pin"]), active_high=alarm_warning_info.get("active_high", True), initial_value=False) if "pin" in alarm_warning_info else None
    alarm_buzzer = OutputDevice(int(alarm_buzzer_info["pin"]), active_high=alarm_buzzer_info.get("active_high", True), initial_value=False) if "pin" in alarm_buzzer_info else None

    controller = MotionController(
        x=x_axis,
        y=y_axis,
        z=z_axis,
        estop=estop_button,
        config=config,
        led_idle=led_idle,
        led_moving=led_moving,
        led_success=led_success,
        alarm_warning=alarm_warning,
        alarm_buzzer=alarm_buzzer,
    )
    controller_ref["controller"] = controller
    return controller


def build_default_controller() -> MotionController:
    return build_controller(build_default_machine_config())
