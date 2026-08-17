from __future__ import annotations

from src.core.backends.base import (
    BackendMetadata,
    BackendRegistration,
    BackendStability,
    ExperimentalEvidence,
)

from .backend import Ite8295ZonesBackend
from .device import Ite8295ZonesKeyboardDevice

BACKEND_REGISTRATION = BackendRegistration(
    metadata=BackendMetadata(
        name="ite8295_zones_lenovo_ideapad",
        priority=97,
        provider="usb-userspace",
        stability=BackendStability.EXPERIMENTAL,
        experimental_evidence=ExperimentalEvidence.REVERSE_ENGINEERED,
    ),
    factory=Ite8295ZonesBackend,
)

__all__ = ["BACKEND_REGISTRATION", "Ite8295ZonesBackend", "Ite8295ZonesKeyboardDevice"]
