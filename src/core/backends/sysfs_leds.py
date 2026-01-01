"""Compatibility wrapper for sysfs LED backend.

The implementation moved to `src.core.backends.sysfs.backend` as part of the
purpose-based backend refactor.
"""

from __future__ import annotations

from .sysfs import SysfsLedsBackend, SysfsLedKeyboardDevice

__all__ = ["SysfsLedsBackend", "SysfsLedKeyboardDevice"]
