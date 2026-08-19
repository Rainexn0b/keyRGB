"""Experimental ITE 8258 24-zone hidraw backend."""

from keyrgb.core.backends.base import (
    BackendMetadata,
    BackendRegistration,
    BackendStability,
    ExperimentalEvidence,
)

from .backend import Ite8258Backend
from .device import Ite8258KeyboardDevice

BACKEND_REGISTRATION = BackendRegistration(
    metadata=BackendMetadata(
        name="ite8258_zones_lenovo_legion",
        priority=98,
        provider="usb-userspace",
        stability=BackendStability.EXPERIMENTAL,
        experimental_evidence=ExperimentalEvidence.REVERSE_ENGINEERED,
    ),
    factory=Ite8258Backend,
)

__all__ = ["BACKEND_REGISTRATION", "Ite8258Backend", "Ite8258KeyboardDevice"]
