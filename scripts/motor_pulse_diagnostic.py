#!/usr/bin/env python3
"""Send a short, bounded pulse burst to one unloaded stepper axis."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from gpiozero import DigitalInputDevice, DigitalOutputDevice


SERVICE_NAME = "narit-vending-web.service"
MAX_DURATION_S = 3.0
MAX_FREQUENCY_HZ = 2_000.0
SWEEP_FREQUENCIES_HZ = (50.0, 100.0, 200.0, 400.0, 800.0, 1_200.0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--axis", choices=("x", "y", "z"), required=True)
    parser.add_argument("--frequency", type=float, default=100.0, help="Pulse frequency in Hz")
    parser.add_argument("--duration", type=float, default=1.0, help="Burst duration in seconds")
    parser.add_argument("--direction-level", choices=("low", "high"), default="high")
    parser.add_argument("--enable-level", choices=("low", "high"), default="high")
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="Try bounded three-second stages across safe frequencies and both enable levels",
    )
    parser.add_argument("--config", type=Path, default=Path("hardware_config.json"))
    parser.add_argument("--confirm-unloaded", action="store_true", required=True)
    return parser.parse_args()


def service_is_active() -> bool:
    result = subprocess.run(
        ("systemctl", "is-active", "--quiet", SERVICE_NAME),
        check=False,
    )
    return result.returncode == 0


def physical_level(value: str) -> bool:
    return value == "high"


def main() -> int:
    args = parse_args()
    if not 10.0 <= args.frequency <= MAX_FREQUENCY_HZ:
        raise SystemExit(f"frequency must be between 10 and {MAX_FREQUENCY_HZ:g} Hz")
    if not 0.1 <= args.duration <= MAX_DURATION_S:
        raise SystemExit(f"duration must be between 0.1 and {MAX_DURATION_S:g} seconds")
    if service_is_active():
        raise SystemExit(f"stop {SERVICE_NAME} before direct GPIO testing")

    config = json.loads(args.config.read_text(encoding="utf-8"))
    motor = config["motors"][args.axis]
    estop_config = config["digital_inputs"]["estop"]
    direction_level = physical_level(args.direction_level)
    configured_enable_level = bool(motor.get("active_high", True))
    profiles = [(args.enable_level, args.frequency, args.duration)]
    if args.sweep:
        profiles = [
            (enable_level, frequency, MAX_DURATION_S)
            for enable_level in ("low", "high")
            for frequency in SWEEP_FREQUENCIES_HZ
        ]

    estop = DigitalInputDevice(
        estop_config["pin"],
        pull_up=estop_config["pull_up"],
    )
    pulse = DigitalOutputDevice(motor["step_pin"], active_high=True, initial_value=False)
    direction = DigitalOutputDevice(motor["dir_pin"], active_high=True, initial_value=False)
    enable = DigitalOutputDevice(
        motor["enable_pin"],
        active_high=True,
        initial_value=not configured_enable_level,
    )

    sent_pulses = 0
    started_at = time.monotonic()
    motion_confirmed = False
    last_profile = profiles[0]
    try:
        if bool(estop.value) == bool(estop_config["active_high"]):
            raise SystemExit("E-Stop is active; pulse test cancelled")

        direction.value = direction_level
        for profile_index, (enable_name, frequency, duration) in enumerate(profiles, start=1):
            last_profile = (enable_name, frequency, duration)
            enable.value = physical_level(enable_name)
            half_period_s = 0.5 / frequency
            requested_pulses = round(frequency * duration)
            print(
                f"STAGE {profile_index}/{len(profiles)} axis={args.axis.upper()} "
                f"frequency={frequency:g}Hz duration={duration:g}s enable={enable_name}",
                flush=True,
            )
            time.sleep(0.25)

            for _ in range(requested_pulses):
                if bool(estop.value) == bool(estop_config["active_high"]):
                    motion_confirmed = True
                    break
                pulse.on()
                time.sleep(half_period_s)
                pulse.off()
                time.sleep(half_period_s)
                sent_pulses += 1
            pulse.off()
            if motion_confirmed:
                break
    finally:
        pulse.off()
        enable.value = not configured_enable_level
        pulse.close()
        direction.close()
        enable.close()
        estop.close()

    elapsed_s = time.monotonic() - started_at
    enable_name, frequency, _ = last_profile
    result = "OPERATOR_CONFIRMED_MOTION" if motion_confirmed else "NO_MOTION_CONFIRMATION"
    print(
        f"result={result} axis={args.axis.upper()} pulses={sent_pulses} "
        f"last_frequency={frequency:g}Hz elapsed={elapsed_s:.3f}s "
        f"dir={args.direction_level} last_enable={enable_name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
