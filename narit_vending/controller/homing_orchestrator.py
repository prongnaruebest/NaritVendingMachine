"""High-level homing orchestration separated from axis pulse execution."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


HomeProgress = Callable[[str, str], None]


class HomingOrchestrator:
    """Coordinate axis homing while each axis retains pulse-level execution."""

    def __init__(
        self,
        *,
        axes: Callable[[], dict[str, Any]],
        home_order: tuple[str, ...],
    ) -> None:
        self._axes = axes
        self._home_order = home_order

    def home_axis(self, axis_name: str, progress: HomeProgress | None = None) -> None:
        axis = self._axes()[axis_name.lower()]
        axis.home(progress=(lambda phase: progress(axis.config.name, phase)) if progress else None)
        self._move_to_home_position(axis, progress)
        if progress:
            progress(axis.config.name, "passed")

    def home_all(self, progress: HomeProgress | None = None) -> None:
        axes = self._axes()
        backend = axes["x"].motion_backend
        protocol = getattr(backend, "expected_protocol", 1) if backend is not None else 1
        parallel_capable = (
            backend is not None
            and isinstance(protocol, (int, float))
            and protocol >= 3
            and hasattr(backend, "home_parallel")
        )
        if not parallel_capable:
            for axis_name in self._home_order:
                self.home_axis(axis_name, progress=progress)
            return

        plans: dict[str, dict[str, Any]] = {}
        for name, axis in axes.items():
            if progress:
                progress(name, "searching")
            plans[name] = {
                "direction": axis.config.home_direction,
                "speed_hz": min(
                    axis.config.max_pulse_hz,
                    axis.config.homing_search_speed_mm_s * axis.config.steps_per_mm,
                ),
                "limit": lambda current=axis: current.head_limit.value,
                "abort": lambda current=axis: bool(current.estop.value or current.stop_requested()),
                "timeout_s": axis.config.homing_timeout_s,
            }
        backend.home_parallel(plans)

        # Preserve the existing precision backoff/latch verification per axis
        # after the parallel search phase.  AxisController remains the sole
        # owner of pulse execution and sensor-level validation.
        for name, axis in axes.items():
            axis.home(progress=(lambda phase, current=name: progress(current, phase)) if progress else None)
            self._move_to_home_position(axis, progress)
            if progress:
                progress(name, "passed")

    @staticmethod
    def _move_to_home_position(axis: Any, progress: HomeProgress | None) -> None:
        if axis.config.home_position_mm <= 0:
            return
        if progress:
            progress(axis.config.name, "positioning")
        try:
            axis.move_to_mm(
                axis.config.home_position_mm,
                speed_mm_s=axis.config.commissioned_max_speed_mm_s,
            )
        except Exception:
            axis.is_homed = False
            raise
