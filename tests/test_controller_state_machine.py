import unittest

from narit_vending.controller.state_machine import (
    MachineState,
    StateMachine,
    StateMachineError,
)
from narit_vending.domain.enums import MachineState as DomainMachineState
from narit_vending.domain.machine_state import normalize_machine_state


class TestStateMachine(unittest.TestCase):
    def test_controller_reexports_canonical_machine_state(self):
        self.assertIs(MachineState, DomainMachineState)

    def test_normalization_uses_authoritative_motion_facts(self):
        self.assertEqual(
            normalize_machine_state("idle", estop=False, busy=False, active_command=None, axes_homed=True),
            MachineState.READY,
        )
        self.assertEqual(
            normalize_machine_state("ready", estop=False, busy=True, active_command="home_all", axes_homed=False),
            MachineState.HOMING,
        )
        self.assertEqual(
            normalize_machine_state("ready", estop=True, busy=False, active_command=None, axes_homed=True),
            MachineState.E_STOP,
        )
    def test_initial_state(self):
        sm = StateMachine()
        self.assertEqual(sm.state, MachineState.STARTING)

    def test_valid_transitions(self):
        sm = StateMachine(MachineState.STARTING)
        sm.transition(MachineState.NOT_READY)
        self.assertEqual(sm.state, MachineState.NOT_READY)

        sm.transition(MachineState.HOMING)
        self.assertEqual(sm.state, MachineState.HOMING)

        sm.transition(MachineState.READY)
        self.assertEqual(sm.state, MachineState.READY)

        sm.transition(MachineState.MOVING)
        self.assertEqual(sm.state, MachineState.MOVING)

        sm.transition(MachineState.READY)
        self.assertEqual(sm.state, MachineState.READY)

    def test_invalid_transition_raises_error(self):
        sm = StateMachine(MachineState.STARTING)
        with self.assertRaises(StateMachineError):
            sm.transition(MachineState.MOVING)  # Cannot jump straight from STARTING to MOVING

    def test_legacy_string_transitions(self):
        sm = StateMachine(MachineState.NOT_READY)
        sm.transition("homing")
        self.assertEqual(sm.state, MachineState.HOMING)

        sm.transition("success")
        self.assertEqual(sm.state, MachineState.READY)

        sm.transition("moving")
        self.assertEqual(sm.state, MachineState.MOVING)

    def test_force_state_overrides_guard(self):
        sm = StateMachine(MachineState.MOVING)
        sm.force(MachineState.E_STOP)
        self.assertEqual(sm.state, MachineState.E_STOP)

    def test_every_runtime_state_has_an_explicit_transition_policy(self):
        from narit_vending.controller.state_machine import _TRANSITIONS

        controller_states = set(MachineState) - {MachineState.CONTROLLER_OFFLINE}
        self.assertEqual(set(_TRANSITIONS), controller_states)


if __name__ == "__main__":
    unittest.main()
