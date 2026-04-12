from __future__ import annotations

from src.core.backends.base import BackendCapabilities
from src.core.backends.sysfs.device import SysfsLedKeyboardDevice


class SysfsMouseDevice(SysfsLedKeyboardDevice):
    """Auxiliary sysfs LED device wrapper for external mice.

    The underlying sysfs implementation can expose multiple zones, but mice are
    still treated as uniform-capable auxiliary devices rather than keyboard-like
    per-key surfaces.
    """

    def capabilities(self) -> BackendCapabilities:
        caps = super().capabilities()
        return BackendCapabilities(
            per_key=False,
            color=bool(caps.color),
            hardware_effects=False,
            palette=False,
        )


__all__ = ["SysfsMouseDevice"]
