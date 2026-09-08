"""Typed domain failures shared by planning, execution and transports."""


class MotionError(RuntimeError):
    """Base class for an expected machine-motion failure."""


class LimitTriggeredError(MotionError):
    """A limit interrupted an operation that cannot safely recover in place."""


class ActiveLimitError(MotionError):
    """The requested direction is blocked by an active endpoint sensor."""


class EmergencyStopError(MotionError):
    """Physical or fail-safe emergency stop is active."""


class NotHomedError(MotionError):
    """A referenced coordinate is required for the requested operation."""


class StopRequestedError(MotionError):
    """The immediate software stop latch interrupted motion."""


class ControlledStopError(MotionError):
    """A hold-to-run or planned controlled stop completed."""


class TravelBoundaryError(MotionError):
    """A command was rejected before motion for exceeding software travel."""


class NucleoError(MotionError):
    """NUCLEO transport, protocol or firmware execution failed."""


class PositionVerificationError(MotionError):
    """Commissioned drive in-position feedback did not verify completion."""
