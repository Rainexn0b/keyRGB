"""Unified per-backend emulation for hardware-free UX and tests.

Emulation intercepts primary selection and secondary-route acquisition. It is
never hardware detection and must not be used as evidence to promote an
experimental backend.
"""

from __future__ import annotations

from .auxiliary import auxiliary_emulation_enabled, route_is_emulated
from .devices import EmulatedKeyboardDevice, reset_emulated_devices
from .primary import EmulatedPrimaryBackend, make_emulated_primary_backend
from .spec import (
    EMULATE_ENVIRONMENT_VARIABLE,
    EmulationError,
    EmulationSpec,
    emulation_enabled,
    emulation_snapshot,
    get_emulation_spec,
    parse_emulate_spec,
)

__all__ = [
    "EMULATE_ENVIRONMENT_VARIABLE",
    "EmulatedKeyboardDevice",
    "EmulatedPrimaryBackend",
    "EmulationError",
    "EmulationSpec",
    "auxiliary_emulation_enabled",
    "emulation_enabled",
    "emulation_snapshot",
    "get_emulation_spec",
    "make_emulated_primary_backend",
    "parse_emulate_spec",
    "reset_emulated_devices",
    "route_is_emulated",
]
