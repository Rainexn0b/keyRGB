"""ITE 8910 backend package.

This package contains KeyRGB's experimental Linux `hidraw` path for
`0x048d:0x8910`, aligned to the public reverse-engineering notes captured in
`docs/developement/backends/ite8910-protocol-notes.md`.
"""

from src.core.backends.base import BackendMetadata, BackendRegistration, BackendStability

from .backend import Ite8910Backend
from .device import Ite8910KeyboardDevice
from .protocol import Ite8910Effect, Ite8910ProtocolState

BACKEND_REGISTRATION = BackendRegistration(
    metadata=BackendMetadata(
        name="ite8910_perkey",
        priority=94,
        provider="usb-userspace",
        stability=BackendStability.VALIDATED,
    ),
    factory=Ite8910Backend,
)

__all__ = [
    "BACKEND_REGISTRATION",
    "Ite8910Backend",
    "Ite8910Effect",
    "Ite8910KeyboardDevice",
    "Ite8910ProtocolState",
]
