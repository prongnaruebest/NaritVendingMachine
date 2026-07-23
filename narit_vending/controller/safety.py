"""Safety Interlock — centralised safety gate for all commands.

ALL commands (HTTP, MQTT, system) must pass through SafetyInterlock.evaluate()
before reaching MotionController or GPIO.  The web process MUST NOT implement
safety logic — it only forwards CommandEnvelopes and displays results.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .state_machine import MachineState

if TYPE_CHECKING:
    from narit_vending.shared.commands import CommandEnvelope
    from narit_vending.shared.snapshot import MachineSnapshot

_log = logging.getLogger(__name__)

# Commands that bypass most safety checks (they ARE the safety response)
_PRIORITY_COMMANDS = frozenset({
    "STOP",
    "E_STOP",
    "CLEAR_ALARM",
    "CONTROLLED_STOP",
})

# Commands that require the machine to be READY (homed + no alarm + no estop)
_MOTION_COMMANDS = frozenset({
    "JOG",
    "MOVE_TO",
    "MOVE_TO_SLOT",
    "DISPENSE",
    "EXECUTE_ARMED_MOVE",
})

# Commands that only require NOT_READY or better (no estop, no alarm)
_HOME_COMMANDS = frozenset({
    "HOME_AXIS",
    "HOME_ALL",
})

# Motor test commands need motor_test_armed
_MOTOR_TEST_COMMANDS = frozenset({
    "RUN_MOTOR_TEST",
})


@dataclass
class SafetyDecision:
    """Result of a safety evaluation."""

    allowed: bool
    reason_codes: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)

    @property
    def reason(self) -> str:
        return "; ".join(self.reason_codes) if self.reason_codes else ""


class SafetyInterlock:
    """Evaluate whether a command is safe to execute given the current snapshot.

    This class has no state of its own — it is a pure function of the
    command + snapshot pair. This makes it trivially unit-testable without
    any GPIO or Flask dependency.
    """

    def evaluate(self, envelope: "CommandEnvelope", snapshot: "MachineSnapshot") -> SafetyDecision:
        """Return a SafetyDecision.  If not allowed, reason_codes explains why."""
        cmd = envelope.command_type

        # Priority commands always pass (STOP/E-STOP cannot be blocked)
        if cmd in _PRIORITY_COMMANDS:
            _log.debug("Safety: PRIORITY command %s — always allowed", cmd)
            return SafetyDecision(allowed=True)

        reasons: list[str] = []
        actions: list[str] = []

        # ── 1. E-Stop ──────────────────────────────────────────────────────────
        if snapshot.estop:
            reasons.append("ESTOP_ACTIVE")
            actions.append("Release physical E-Stop button")

        # ── 2. Stop latch ──────────────────────────────────────────────────────
        if snapshot.stop_requested:
            reasons.append("STOP_LATCH_ACTIVE")
            actions.append("Clear alarms before issuing motion commands")

        # ── 3. Config restart required ─────────────────────────────────────────
        if snapshot.configuration_restart_required and cmd not in ("ARM_MOTOR_TEST", "DISARM_MOTOR_TEST"):
            reasons.append("CONFIG_RESTART_REQUIRED")
            actions.append("Apply configuration changes and restart the controller")

        # ── 4. Busy with another motion command ────────────────────────────────
        if snapshot.busy and cmd not in _PRIORITY_COMMANDS:
            reasons.append("MACHINE_BUSY")
            actions.append("Wait for current command to complete or issue STOP")

        # ── 5. Motor test armed blocks normal motion ───────────────────────────
        if snapshot.motor_test_armed and cmd in _MOTION_COMMANDS | _HOME_COMMANDS:
            reasons.append("MOTOR_TEST_ARMED")
            actions.append("Disarm Motor Test Mode before issuing normal motion commands")

        # ── 6. State-specific checks ───────────────────────────────────────────
        state = snapshot.state
        if cmd in _MOTION_COMMANDS:
            # Require READY state for motion
            if state != MachineState.READY.value:
                if state == MachineState.E_STOP.value:
                    reasons.append("STATE_ESTOP")
                elif state == MachineState.ALARM.value:
                    reasons.append("STATE_ALARM")
                elif state in (MachineState.NOT_READY.value, MachineState.HOMING.value):
                    reasons.append("AXES_NOT_HOMED")
                    actions.append("Home all axes before motion")
                else:
                    reasons.append(f"STATE_NOT_READY:{state}")

            # Check individual axis limits
            for axis_name in ("x", "y", "z"):
                axis = snapshot.axes.get(axis_name)
                if axis and axis.head_limit and axis.tail_limit:
                    reasons.append(f"LIMIT_CONFLICT_{axis_name.upper()}")
                    actions.append(f"{axis_name.upper()} axis has conflicting limit inputs — hardware fault")

        if cmd in _HOME_COMMANDS:
            if state in (MachineState.E_STOP.value, MachineState.ALARM.value):
                reasons.append(f"STATE_{state}_BLOCKS_HOME")
                actions.append("Clear alarm before homing")

        if cmd in _MOTOR_TEST_COMMANDS:
            if not snapshot.motor_test_armed:
                reasons.append("MOTOR_TEST_NOT_ARMED")
                actions.append("Arm Motor Test Mode first")
            if snapshot.estop:
                reasons.append("ESTOP_ACTIVE")

        allowed = len(reasons) == 0
        if not allowed:
            _log.warning("Safety REJECTED %s: %s", cmd, "; ".join(reasons))
        else:
            _log.debug("Safety OK: %s", cmd)
        return SafetyDecision(allowed=allowed, reason_codes=reasons, required_actions=actions)
