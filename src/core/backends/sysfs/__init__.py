"""Sysfs LED subsystem backend (brightness-only or multi-color)."""

from src.core.backends.base import BackendMetadata, BackendRegistration, BackendStability

from .backend import SysfsLedsBackend
from .device import SysfsLedKeyboardDevice

BACKEND_REGISTRATION = BackendRegistration(
    metadata=BackendMetadata(
        name="sysfs-leds",
        priority=150,
        provider="kernel-sysfs",
        stability=BackendStability.VALIDATED,
    ),
    factory=SysfsLedsBackend,
)

__all__ = ["BACKEND_REGISTRATION", "SysfsLedKeyboardDevice", "SysfsLedsBackend"]
