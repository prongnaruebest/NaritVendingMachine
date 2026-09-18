"""Configuration models and loading utilities for the Narit Vending Machine."""

from __future__ import annotations

from .motion import (
    AxisConfig,
    MachineConfig,
    SlotPosition,
    SlotSequenceConfig,
    build_default_machine_config,
    build_default_slots,
    load_hardware_config,
    load_machine_config,
    save_machine_config,
)

__all__ = [
    "AxisConfig",
    "MachineConfig",
    "SlotPosition",
    "SlotSequenceConfig",
    "build_default_machine_config",
    "build_default_slots",
    "load_hardware_config",
    "load_machine_config",
    "save_machine_config",
]

