import unittest

from narit_vending.controller.state_machine import (
    MachineState,
    StateMachine,
    StateMachineError,
)


class TestStateMachine(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
