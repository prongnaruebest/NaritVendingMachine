from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager

from .motion import (
    EmergencyStopError,
    LimitTriggeredError,
    MotionController,
    MotionError,
    NotHomedError,
    build_default_controller,
    load_machine_config,
    build_controller,
)

try:
    import termios
    import tty
except ImportError:  # pragma: no cover - only happens on non-POSIX dev machines
    termios = None
    tty = None


@contextmanager
def raw_keyboard() -> object:
    if termios is None or tty is None:
        raise MotionError("manual jog requires a POSIX terminal such as Raspberry Pi Linux")
    fd = sys.stdin.fileno()
    original = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, original)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Narit Vending motion controller")
    parser.add_argument("--config", default="machine_config.json", help="Path to machine configuration JSON")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show live status of all axes")
    subparsers.add_parser("home", help="Home all axes in configured order")

    jog_parser = subparsers.add_parser("jog", help="Manual jog with keyboard")
    jog_parser.add_argument("--step-mm", type=float, default=None, help="Override jog step for all axes")

    move_parser = subparsers.add_parser("move", help="Move by relative distance in mm")
    move_parser.add_argument("--x", type=float, default=0.0)
    move_parser.add_argument("--y", type=float, default=0.0)
    move_parser.add_argument("--z", type=float, default=0.0)

    goto_parser = subparsers.add_parser("goto-slot", help="Move to a configured vending slot")
    goto_parser.add_argument("slot", help="Slot number such as 1 or 30")

    return parser


def interactive_jog(controller: MotionController, step_override_mm: float | None) -> None:
    print("Manual jog mode")
    print("  a/d = X -/+")
    print("  s/w = Y -/+")
    print("  f/r = Z -/+")
    print("  h = home all")
    print("  p = print status")
    print("  q = quit")
    print("Press keys to move...")

    axis_steps = {
        "x": step_override_mm or controller.x.config.jog_step_mm,
        "y": step_override_mm or controller.y.config.jog_step_mm,
        "z": step_override_mm or controller.z.config.jog_step_mm,
    }

    with raw_keyboard():
        while True:
            key = sys.stdin.read(1).lower()
            if key == "q":
                print("\nLeaving jog mode.")
                return
            try:
                if key == "a":
                    controller.x.move_mm(-axis_steps["x"])
                elif key == "d":
                    controller.x.move_mm(axis_steps["x"])
                elif key == "s":
                    controller.y.move_mm(-axis_steps["y"])
                elif key == "w":
                    controller.y.move_mm(axis_steps["y"])
                elif key == "f":
                    controller.z.move_mm(-axis_steps["z"])
                elif key == "r":
                    controller.z.move_mm(axis_steps["z"])
                elif key == "h":
                    print("\nHoming all axes...")
                    controller.home_all()
                elif key == "p":
                    print(f"\n{json.dumps(controller.status(), indent=2)}")
                    continue
                else:
                    continue
                print(
                    "\r"
                    f"X={controller.x.position_mm:.2f}mm "
                    f"Y={controller.y.position_mm:.2f}mm "
                    f"Z={controller.z.position_mm:.2f}mm    ",
                    end="",
                    flush=True,
                )
            except (EmergencyStopError, LimitTriggeredError, MotionError) as exc:
                print(f"\n{exc}")


def run_command(args: argparse.Namespace) -> int:
    try:
        machine_config = load_machine_config(args.config)
        controller = build_controller(machine_config)
    except FileNotFoundError:
        controller = build_default_controller()

    try:
        if args.command == "status":
            print(json.dumps(controller.status(), indent=2))
            return 0
        if args.command == "home":
            controller.home_all()
            print(json.dumps(controller.status(), indent=2))
            return 0
        if args.command == "jog":
            interactive_jog(controller, args.step_mm)
            return 0
        if args.command == "move":
            controller.home_all()
            controller.move_by_mm(x_mm=args.x, y_mm=args.y, z_mm=args.z)
            print(json.dumps(controller.status(), indent=2))
            return 0
        if args.command == "goto-slot":
            controller.home_all()
            slot = controller.move_to_slot(args.slot)
            print(f"Moved to slot {slot.code}: x={slot.x_mm:.2f} y={slot.y_mm:.2f} z={slot.z_mm:.2f}")
            print(json.dumps(controller.status(), indent=2))
            return 0
    except (EmergencyStopError, LimitTriggeredError, MotionError, NotHomedError) as exc:
        print(exc, file=sys.stderr)
        return 1

    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return run_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
