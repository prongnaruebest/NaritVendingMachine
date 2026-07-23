"""Controller process entry point.

Usage:
    python -m narit_vending.controller [options]
    python -m narit_vending.controller --mock-gpio   # for dev/CI without GPIO

Startup sequence:
    1. Parse args and configure logging
    2. Instantiate MotionService (existing — owns GPIO + motion)
    3. Build StateMachine (wraps MotionService state)
    4. Build CommandBus and register all handlers
    5. Start asyncio IPC server (Unix socket or TCP)
    6. Run event loop indefinitely
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from narit_vending.shared.snapshot import MachineSnapshot

_log = logging.getLogger("narit_vending.controller")


def _build_snapshot(service: Any) -> MachineSnapshot:
    """Convert MotionService state into a MachineSnapshot."""
    from narit_vending.shared.snapshot import AxisSnapshot, MachineSnapshot

    status = service.status_payload()
    ctrl_status = status.get("status", {})

    axes = {}
    for ax in ("x", "y", "z"):
        ax_data = ctrl_status.get(ax, {})
        axes[ax] = AxisSnapshot(
            name=ax,
            position_mm=float(ax_data.get("position_mm", 0.0)),
            position_steps=int(ax_data.get("position_steps", 0)),
            is_homed=bool(ax_data.get("is_homed", False)),
            head_limit=bool(ax_data.get("head_limit", False)),
            tail_limit=bool(ax_data.get("tail_limit", False)),
        )

    safety = status.get("safety", {})
    op = status.get("operation", {})
    mc = status.get("motion_command", {})

    # Map legacy machine_state strings to MachineState enum values
    raw_state = str(status.get("machine_state", "NOT_READY")).upper()

    return MachineSnapshot(
        state=raw_state,
        estop=bool(ctrl_status.get("estop", False)),
        axes=axes,
        busy=bool(status.get("busy", False)),
        active_command=status.get("active_command"),
        command_id=mc.get("command_id"),
        command_started_at=mc.get("started_at"),
        command_estimated_duration_s=mc.get("estimated_duration_s"),
        operation_phase=str(op.get("phase", "ready")),
        operation_message=str(op.get("message", "")),
        operation_axis=op.get("active_axis"),
        homing=dict(op.get("homing", {})),
        last_error=str(status.get("last_error", "")),
        alarm_channels=list(status.get("alarm_channels", [])),
        config_revision=str(getattr(service, "config_report", None) and service.config_report.revision or ""),
        motor_test_armed=bool(safety.get("motor_test", {}).get("armed", False)),
        configuration_restart_required=bool(safety.get("configuration_restart_required", False)),
        stop_requested=bool(safety.get("stop_requested", False)),
        controlled_stop_requested=bool(safety.get("controlled_stop_requested", False)),
        speed_override=getattr(service.controller, "speed_override", None),
    )


def _register_handlers(bus: Any, service: Any) -> None:
    """Register all command handlers on the command bus."""
    from narit_vending.controller.handlers.home import (
        make_home_all_handler,
        make_home_axis_handler,
    )
    from narit_vending.controller.handlers.jog import make_jog_handler
    from narit_vending.controller.handlers.motor_test import (
        make_arm_motor_test_handler,
        make_disarm_motor_test_handler,
        make_run_motor_test_handler,
    )
    from narit_vending.controller.handlers.move import (
        make_arm_move_handler,
        make_dispense_handler,
        make_execute_armed_move_handler,
        make_move_to_handler,
        make_move_to_slot_handler,
        make_plan_move_handler,
        make_validate_target_handler,
    )
    from narit_vending.controller.handlers.stop import (
        make_clear_alarm_handler,
        make_controlled_stop_handler,
        make_stop_handler,
    )

    bus.register("STOP", make_stop_handler(service))
    bus.register("E_STOP", make_stop_handler(service))  # same effect
    bus.register("CONTROLLED_STOP", make_controlled_stop_handler(service))
    bus.register("CLEAR_ALARM", make_clear_alarm_handler(service))
    bus.register("HOME_AXIS", make_home_axis_handler(service))
    bus.register("HOME_ALL", make_home_all_handler(service))
    bus.register("JOG", make_jog_handler(service))
    bus.register("MOVE_TO", make_move_to_handler(service))
    bus.register("MOVE_TO_SLOT", make_move_to_slot_handler(service))
    bus.register("DISPENSE", make_dispense_handler(service))
    bus.register("VALIDATE_TARGET", make_validate_target_handler(service))
    bus.register("ARM_MOVE", make_arm_move_handler(service))
    bus.register("EXECUTE_ARMED_MOVE", make_execute_armed_move_handler(service))
    bus.register("PLAN_MOVE", make_plan_move_handler(service))
    bus.register("ARM_MOTOR_TEST", make_arm_motor_test_handler(service))
    bus.register("DISARM_MOTOR_TEST", make_disarm_motor_test_handler(service))
    bus.register("RUN_MOTOR_TEST", make_run_motor_test_handler(service))
    _log.info("Registered %d command handlers", len(bus._handlers))


async def _async_main(service: Any, args: argparse.Namespace) -> None:
    from narit_vending.controller.command_bus import CommandBus
    from narit_vending.controller.server import IPCServer
    from narit_vending.controller.state_machine import StateMachine

    state_machine = StateMachine()
    snapshot_fn = lambda: _build_snapshot(service)  # noqa: E731
    bus = CommandBus(state_machine, snapshot_fn)
    _register_handlers(bus, service)

    ipc = IPCServer(
        command_bus=bus,
        snapshot_fn=snapshot_fn,
        config_fn=service.get_config,
        save_config_fn=service.save_configuration,
    )
    await ipc.start()
    _log.info("Controller IPC server ready — state machine: %s", state_machine.state.value)

    stop_event = asyncio.Event()

    def _handle_signal(*_: Any) -> None:
        _log.info("Signal received — stopping controller")
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            # Windows: signals not supported in asyncio
            signal.signal(sig, _handle_signal)

    await stop_event.wait()
    _log.info("Shutting down IPC server")
    await ipc.stop()
    service.mqtt_service.stop()
    _log.info("Controller stopped")


def main() -> None:
    parser = argparse.ArgumentParser(description="NARIT Vending Controller Process")
    parser.add_argument(
        "--config",
        default="machine_config.json",
        help="Path to machine_config.json",
    )
    parser.add_argument(
        "--hw-config",
        default="hardware_config.json",
        help="Path to hardware_config.json",
    )
    parser.add_argument(
        "--mock-gpio",
        action="store_true",
        help="Use mock GPIO (no physical hardware required)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    if args.mock_gpio:
        os.environ.setdefault("GPIOZERO_PIN_FACTORY", "mock")
        _log.info("Mock GPIO mode enabled")

    _log.info(
        "Starting controller — config=%s hw=%s", args.config, args.hw_config
    )

    # Import webapp MotionService (existing monolith — owns GPIO + motion)
    from narit_vending.webapp import MotionService

    try:
        service = MotionService(config_path=args.config, hw_config_path=args.hw_config)
    except Exception as exc:
        _log.critical("Controller startup failed: %s", exc)
        sys.exit(1)

    _log.info("MotionService initialized — running IPC server")
    asyncio.run(_async_main(service, args))


if __name__ == "__main__":
    main()
