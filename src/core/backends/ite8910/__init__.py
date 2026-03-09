"""ITE 8910 / ITE 829x backend package.

This package contains the Python translation of the public `ite-829x`
userspace reference for `0x048d:0x8910` plus the Linux `hidraw` transport used
by KeyRGB's experimental rollout path.
"""

from .backend import Ite8910Backend
from .device import Ite8910KeyboardDevice
from .protocol import Ite8910Effect, Ite8910ProtocolState

__all__ = [
    "Ite8910Backend",
    "Ite8910Effect",
    "Ite8910KeyboardDevice",
    "Ite8910ProtocolState",
]