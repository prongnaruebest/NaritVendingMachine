from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


AXES = ("x", "y", "z")
CONFIG_SCHEMA_VERSION = 1
MOTION_OVERRIDE_FIELDS = (
    "steps_per_mm",
    "max_travel_mm",
    "max_speed_mm_s",
    "default_speed_mm_s",
    "acceleration",
    "deceleration",
    "settle_delay",
    "jog_step_mm",
    "home_direction",
    "forward_direction",
    "lead_screw_pitch_mm",
    "motor_steps_per_rev",
    "driver_microsteps",
)


@dataclass(frozen=True)
class ConfigIssue:
    severity: str
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True)
class ConfigReport:
    valid: bool
    revision: str
    generated_at: str
    issues: tuple[ConfigIssue, ...]
    effective_axes: dict[str, dict[str, object]]
    sources: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": CONFIG_SCHEMA_VERSION,
            "valid": self.valid,
            "revision": self.revision,
            "generated_at": self.generated_at,
            "issues": [issue.to_dict() for issue in self.issues],
            "issue_counts": {
                "errors": sum(issue.severity == "error" for issue in self.issues),
                "warnings": sum(issue.severity == "warning" for issue in self.issues),
            },
            "effective_axes": self.effective_axes,
            "sources": self.sources,
        }


def _canonical_hash(*payloads: dict[str, object]) -> str:
    digest = hashlib.sha256()
    for payload in payloads:
        digest.update(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _load_json_object(path: Path, label: str) -> tuple[dict[str, object], list[ConfigIssue]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, [ConfigIssue("error", "CONFIG_FILE_MISSING", label, f"{path} does not exist")]
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [ConfigIssue("error", "CONFIG_FILE_INVALID", label, str(exc))]
    if not isinstance(payload, dict):
        return {}, [ConfigIssue("error", "CONFIG_ROOT_INVALID", label, "Root value must be an object")]
    return payload, []


def validate_configuration_files(machine_path: str | Path, hardware_path: str | Path) -> ConfigReport:
    machine_file = Path(machine_path)
    hardware_file = Path(hardware_path)
    machine, machine_issues = _load_json_object(machine_file, "machine")
    hardware, hardware_issues = _load_json_object(hardware_file, "hardware")
    return validate_configuration_payloads(
        machine,
        hardware,
        initial_issues=machine_issues + hardware_issues,
        sources={"machine": str(machine_file.resolve()), "hardware": str(hardware_file.resolve())},
    )


def validate_configuration_payloads(
    machine: dict[str, object],
    hardware: dict[str, object],
    *,
    initial_issues: Iterable[ConfigIssue] = (),
    sources: dict[str, str] | None = None,
) -> ConfigReport:
    issues = list(initial_issues)
    machine_axes = machine.get("axes")
    motors = hardware.get("motors")
    inputs = hardware.get("digital_inputs")
    outputs = hardware.get("digital_outputs")
    machine_parameters = hardware.get("machine_parameters")

    if not isinstance(machine_axes, dict):
        issues.append(ConfigIssue("error", "MACHINE_AXES_MISSING", "machine.axes", "axes object is required"))
        machine_axes = {}
    if not isinstance(motors, dict):
        issues.append(ConfigIssue("error", "MOTORS_MISSING", "hardware.motors", "motors object is required"))
        motors = {}
    if not isinstance(inputs, dict):
        issues.append(ConfigIssue("error", "INPUTS_MISSING", "hardware.digital_inputs", "digital_inputs object is required"))
        inputs = {}
    if not isinstance(outputs, dict):
        issues.append(ConfigIssue("error", "OUTPUTS_MISSING", "hardware.digital_outputs", "digital_outputs object is required"))
        outputs = {}
    if not isinstance(machine_parameters, dict):
        machine_parameters = {}
    parameter_axes = machine_parameters.get("axes", {})
    if not isinstance(parameter_axes, dict):
        issues.append(
            ConfigIssue("error", "PARAMETER_AXES_INVALID", "hardware.machine_parameters.axes", "axes must be an object")
        )
        parameter_axes = {}

    effective_axes: dict[str, dict[str, object]] = {}
    for axis in AXES:
        base = machine_axes.get(axis)
        motor = motors.get(axis)
        overrides = parameter_axes.get(axis, {})
        if not isinstance(base, dict):
            issues.append(ConfigIssue("error", "AXIS_CONFIG_MISSING", f"machine.axes.{axis}", "axis object is required"))
            base = {}
        if not isinstance(motor, dict):
            issues.append(ConfigIssue("error", "MOTOR_CONFIG_MISSING", f"hardware.motors.{axis}", "motor object is required"))
            motor = {}
        if not isinstance(overrides, dict):
            issues.append(
                ConfigIssue("error", "AXIS_OVERRIDE_INVALID", f"hardware.machine_parameters.axes.{axis}", "axis must be an object")
            )
            overrides = {}

        effective = dict(base)
        pin_mapping = {
            "pulse_pin": motor.get("step_pin", base.get("pulse_pin")),
            "direction_pin": motor.get("dir_pin", base.get("direction_pin")),
            "enable_pin": motor.get("enable_pin", base.get("enable_pin")),
            "head_limit_pin": _signal_pin(inputs, f"lim_{axis}_head", f"home_sensor_{axis}", base.get("head_limit_pin")),
            "tail_limit_pin": _signal_pin(inputs, f"lim_{axis}_tail", None, base.get("tail_limit_pin")),
        }
        effective.update(pin_mapping)
        effective.update(overrides)
        effective_axes[axis] = effective

        for field, hardware_field in (("pulse_pin", "step_pin"), ("direction_pin", "dir_pin"), ("enable_pin", "enable_pin")):
            if field in base and hardware_field in motor and base[field] != motor[hardware_field]:
                issues.append(
                    ConfigIssue(
                        "warning",
                        "HARDWARE_OVERRIDE",
                        f"effective.axes.{axis}.{field}",
                        f"machine value {base[field]!r} is overridden by hardware value {motor[hardware_field]!r}",
                    )
                )
        for field, signal_name in (("head_limit_pin", f"lim_{axis}_head"), ("tail_limit_pin", f"lim_{axis}_tail")):
            signal = inputs.get(signal_name)
            if isinstance(signal, dict) and field in base and "pin" in signal and base[field] != signal["pin"]:
                issues.append(
                    ConfigIssue(
                        "warning",
                        "SENSOR_PIN_OVERRIDE",
                        f"effective.axes.{axis}.{field}",
                        f"machine value {base[field]!r} is overridden by hardware value {signal['pin']!r}",
                    )
                )
        for field in MOTION_OVERRIDE_FIELDS:
            if field in base and field in overrides and base[field] != overrides[field]:
                issues.append(
                    ConfigIssue(
                        "warning",
                        "MACHINE_PARAMETER_OVERRIDE",
                        f"effective.axes.{axis}.{field}",
                        f"machine value {base[field]!r} is overridden by hardware value {overrides[field]!r}",
                    )
                )

        _validate_axis_values(axis, effective, issues)

    _validate_signal_polarity(inputs, issues)
    _validate_pin_assignments(motors, inputs, outputs, issues)
    _validate_iriv_io(hardware.get("iriv_io"), issues)
    _validate_nucleo(hardware.get("nucleo"), issues)

    revision = _canonical_hash(machine, hardware)
    return ConfigReport(
        valid=not any(issue.severity == "error" for issue in issues),
        revision=revision,
        generated_at=datetime.now(timezone.utc).isoformat(),
        issues=tuple(issues),
        effective_axes=effective_axes,
        sources=sources or {"machine": "memory", "hardware": "memory"},
    )


def _signal_pin(
    inputs: dict[str, object],
    primary_name: str,
    fallback_name: str | None,
    default: object,
) -> object:
    signal = inputs.get(primary_name)
    if not isinstance(signal, dict) and fallback_name is not None:
        signal = inputs.get(fallback_name)
    return signal.get("pin", default) if isinstance(signal, dict) else default


def _validate_axis_values(axis: str, payload: dict[str, object], issues: list[ConfigIssue]) -> None:
    required_positive = (
        "steps_per_mm",
        "max_travel_mm",
        "max_speed_mm_s",
        "default_speed_mm_s",
        "lead_screw_pitch_mm",
        "motor_steps_per_rev",
        "driver_microsteps",
    )
    for field in required_positive:
        try:
            value = float(payload[field])
        except (KeyError, TypeError, ValueError):
            issues.append(ConfigIssue("error", "AXIS_VALUE_INVALID", f"effective.axes.{axis}.{field}", "positive number is required"))
            continue
        if value <= 0:
            issues.append(ConfigIssue("error", "AXIS_VALUE_INVALID", f"effective.axes.{axis}.{field}", "value must be greater than zero"))

    try:
        if float(payload["default_speed_mm_s"]) > float(payload["max_speed_mm_s"]):
            issues.append(
                ConfigIssue("error", "DEFAULT_SPEED_EXCEEDS_MAX", f"effective.axes.{axis}", "default speed cannot exceed max speed")
            )
    except (KeyError, TypeError, ValueError):
        pass
    for field in ("home_direction", "forward_direction"):
        if payload.get(field) not in (0, 1):
            issues.append(ConfigIssue("error", "DIRECTION_INVALID", f"effective.axes.{axis}.{field}", "direction must be 0 or 1"))
    if payload.get("home_direction") == payload.get("forward_direction"):
        issues.append(ConfigIssue("error", "DIRECTION_CONFLICT", f"effective.axes.{axis}", "home and forward directions must be opposite"))


def _validate_signal_polarity(inputs: dict[str, object], issues: list[ConfigIssue]) -> None:
    for name, value in inputs.items():
        if not isinstance(value, dict):
            issues.append(ConfigIssue("error", "INPUT_INVALID", f"hardware.digital_inputs.{name}", "signal must be an object"))
            continue
        pull_up = value.get("pull_up")
        active_high = value.get("active_high")
        if pull_up is not None and isinstance(pull_up, bool) and isinstance(active_high, bool) and active_high != (not pull_up):
            issues.append(
                ConfigIssue(
                    "error",
                    "INPUT_POLARITY_CONFLICT",
                    f"hardware.digital_inputs.{name}",
                    f"active_high must be {str(not pull_up).lower()} when pull_up is {str(pull_up).lower()}",
                )
            )


def _validate_pin_assignments(
    motors: dict[str, object],
    inputs: dict[str, object],
    outputs: dict[str, object],
    issues: list[ConfigIssue],
) -> None:
    assignments: dict[int, list[str]] = {}

    def add(pin_value: object, path: str) -> None:
        try:
            pin = int(pin_value)
        except (TypeError, ValueError):
            issues.append(ConfigIssue("error", "GPIO_PIN_INVALID", path, "GPIO pin must be an integer"))
            return
        if not 0 <= pin <= 27:
            issues.append(ConfigIssue("error", "GPIO_PIN_RANGE", path, "GPIO pin must be within 0-27"))
        assignments.setdefault(pin, []).append(path)

    for axis, value in motors.items():
        if not isinstance(value, dict):
            continue
        for key in ("step_pin", "dir_pin", "enable_pin"):
            if key in value:
                add(value[key], f"hardware.motors.{axis}.{key}")
    for group_name, group in (("digital_inputs", inputs), ("digital_outputs", outputs)):
        for name, value in group.items():
            if isinstance(value, dict) and "pin" in value:
                add(value["pin"], f"hardware.{group_name}.{name}")

    for pin, paths in assignments.items():
        if len(paths) <= 1 or _is_allowed_home_alias(paths):
            continue
        issues.append(ConfigIssue("error", "GPIO_PIN_COLLISION", f"GPIO.{pin}", ", ".join(paths)))


def _validate_iriv_io(payload: object, issues: list[ConfigIssue]) -> None:
    if payload is None:
        return
    if not isinstance(payload, dict):
        issues.append(ConfigIssue("error", "IRIV_IO_INVALID", "hardware.iriv_io", "iriv_io must be an object"))
        return
    if not payload.get("enabled"):
        return
    if not str(payload.get("host", "")).strip():
        issues.append(ConfigIssue("error", "IRIV_IO_HOST_MISSING", "hardware.iriv_io.host", "host is required"))
    for field, minimum, maximum in (("port", 1, 65535), ("unit_id", 0, 255)):
        try:
            value = int(payload[field])
        except (KeyError, TypeError, ValueError):
            issues.append(ConfigIssue("error", "IRIV_IO_VALUE_INVALID", f"hardware.iriv_io.{field}", "integer is required"))
            continue
        if not minimum <= value <= maximum:
            issues.append(ConfigIssue("error", "IRIV_IO_VALUE_RANGE", f"hardware.iriv_io.{field}", f"must be {minimum}-{maximum}"))

    required_inputs = {
        "estop", "x_head_limit", "x_tail_limit", "y_head_limit", "y_tail_limit",
        "z_head_limit", "z_tail_limit", "x_alarm", "y_alarm", "z_alarm", "door",
    }
    inputs = payload.get("inputs")
    outputs = payload.get("outputs")
    if not isinstance(inputs, dict):
        issues.append(ConfigIssue("error", "IRIV_INPUTS_MISSING", "hardware.iriv_io.inputs", "inputs object is required"))
        inputs = {}
    if not isinstance(outputs, dict):
        issues.append(ConfigIssue("error", "IRIV_OUTPUTS_MISSING", "hardware.iriv_io.outputs", "outputs object is required"))
        outputs = {}
    for name in sorted(required_inputs - set(inputs)):
        issues.append(ConfigIssue("error", "IRIV_INPUT_MISSING", f"hardware.iriv_io.inputs.{name}", "required mapping is missing"))
    for name in sorted({"ready", "moving", "alarm", "dispense"} - set(outputs)):
        issues.append(ConfigIssue("error", "IRIV_OUTPUT_MISSING", f"hardware.iriv_io.outputs.{name}", "required mapping is missing"))

    def validate_channels(group: dict[str, object], group_name: str, maximum: int) -> None:
        used: dict[int, str] = {}
        for name, info in group.items():
            if not isinstance(info, dict):
                issues.append(ConfigIssue("error", "IRIV_CHANNEL_INVALID", f"hardware.iriv_io.{group_name}.{name}", "mapping must be an object"))
                continue
            try:
                channel = int(info["channel"])
            except (KeyError, TypeError, ValueError):
                issues.append(ConfigIssue("error", "IRIV_CHANNEL_INVALID", f"hardware.iriv_io.{group_name}.{name}.channel", "integer is required"))
                continue
            if not 0 <= channel <= maximum:
                issues.append(ConfigIssue("error", "IRIV_CHANNEL_RANGE", f"hardware.iriv_io.{group_name}.{name}.channel", f"must be 0-{maximum}"))
            if channel in used:
                issues.append(ConfigIssue("error", "IRIV_CHANNEL_COLLISION", f"hardware.iriv_io.{group_name}.{name}.channel", f"also used by {used[channel]}"))
            used[channel] = name

    validate_channels(inputs, "inputs", 10)
    validate_channels(outputs, "outputs", 3)


def _validate_nucleo(payload: object, issues: list[ConfigIssue]) -> None:
    if payload is None:
        return
    if not isinstance(payload, dict):
        issues.append(ConfigIssue("error", "NUCLEO_INVALID", "hardware.nucleo", "nucleo must be an object"))
        return
    if not payload.get("enabled"):
        return
    if payload.get("transport") != "usb_serial":
        issues.append(
            ConfigIssue("error", "NUCLEO_TRANSPORT_INVALID", "hardware.nucleo.transport", "must be usb_serial")
        )
    if not str(payload.get("port", "")).strip():
        issues.append(ConfigIssue("error", "NUCLEO_PORT_MISSING", "hardware.nucleo.port", "port is required"))
    if str(payload.get("expected_device", "")) != "NUCLEO-F439ZI":
        issues.append(
            ConfigIssue(
                "error",
                "NUCLEO_IDENTITY_INVALID",
                "hardware.nucleo.expected_device",
                "must be NUCLEO-F439ZI",
            )
        )
    for field, minimum, maximum in (("baudrate", 1200, 3_000_000), ("protocol_version", 1, 255)):
        try:
            value = int(payload[field])
        except (KeyError, TypeError, ValueError):
            issues.append(ConfigIssue("error", "NUCLEO_VALUE_INVALID", f"hardware.nucleo.{field}", "integer is required"))
            continue
        if not minimum <= value <= maximum:
            issues.append(
                ConfigIssue(
                    "error",
                    "NUCLEO_VALUE_RANGE",
                    f"hardware.nucleo.{field}",
                    f"must be {minimum}-{maximum}",
                )
            )


def _is_allowed_home_alias(paths: list[str]) -> bool:
    if len(paths) != 2:
        return False
    for axis in AXES:
        expected = {
            f"hardware.digital_inputs.home_sensor_{axis}",
            f"hardware.digital_inputs.lim_{axis}_head",
        }
        if set(paths) == expected:
            return True
    return False


def create_config_backup(
    paths: Iterable[str | Path],
    backup_root: str | Path,
    *,
    reason: str,
) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    destination = Path(backup_root) / timestamp
    destination.mkdir(parents=True, exist_ok=False)
    manifest: dict[str, object] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "files": [],
    }
    for value in paths:
        source = Path(value)
        if not source.exists():
            continue
        target = destination / source.name
        shutil.copy2(source, target)
        manifest["files"].append(
            {
                "source": str(source.resolve()),
                "backup": target.name,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return destination


def restore_config_backup(backup: str | Path, targets: dict[str, str | Path]) -> tuple[Path, ...]:
    backup_path = Path(backup)
    manifest_path = backup_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Backup manifest does not contain files")

    verified: list[tuple[Path, Path]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Backup manifest contains an invalid file entry")
        backup_name = str(entry.get("backup", ""))
        expected_hash = str(entry.get("sha256", ""))
        target_value = targets.get(backup_name)
        if target_value is None:
            continue
        source = backup_path / backup_name
        if source.parent != backup_path or not source.is_file():
            raise ValueError(f"Backup file is missing or unsafe: {backup_name}")
        actual_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise ValueError(f"Backup checksum mismatch: {backup_name}")
        verified.append((source, Path(target_value)))
    if not verified:
        raise ValueError("No requested files were found in the backup")

    previous: dict[Path, bytes | None] = {
        target: target.read_bytes() if target.exists() else None for _, target in verified
    }
    temporary_paths: list[Path] = []
    try:
        for source, target in verified:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.restore.tmp")
            temporary.write_bytes(source.read_bytes())
            temporary_paths.append(temporary)
        for (_, target), temporary in zip(verified, temporary_paths, strict=True):
            os.replace(temporary, target)
    except Exception:
        for target, content in previous.items():
            if content is None:
                target.unlink(missing_ok=True)
            else:
                temporary = target.with_name(f".{target.name}.rollback.tmp")
                temporary.write_bytes(content)
                os.replace(temporary, target)
        raise
    finally:
        for temporary in temporary_paths:
            temporary.unlink(missing_ok=True)
    return tuple(target for _, target in verified)
