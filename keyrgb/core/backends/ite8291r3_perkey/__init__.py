"""ITE 8291r3 USB RGB keyboard backend.

This package name is intentionally explicit about the protocol dialect.
"""

from keyrgb.core.backends.base import BackendMetadata, BackendRegistration, BackendStability

from .backend import Ite8291r3Backend

BACKEND_REGISTRATION = BackendRegistration(
    metadata=BackendMetadata(
        name="ite8291r3_perkey",
        priority=100,
        provider="usb-userspace",
        stability=BackendStability.VALIDATED,
    ),
    factory=Ite8291r3Backend,
)

__all__ = ["BACKEND_REGISTRATION", "Ite8291r3Backend"]
