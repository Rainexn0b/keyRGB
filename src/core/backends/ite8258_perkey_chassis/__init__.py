from __future__ import annotations

from src.core.backends.base import (
    BackendMetadata,
    BackendRegistration,
    BackendStability,
    ExperimentalEvidence,
)

from .backend import Ite8258ChassisBackend

BACKEND_REGISTRATION = BackendRegistration(
    metadata=BackendMetadata(
        name="ite8258_perkey_chassis",
        priority=97,
        provider="usb-userspace",
        stability=BackendStability.EXPERIMENTAL,
        experimental_evidence=ExperimentalEvidence.REVERSE_ENGINEERED,
    ),
    factory=Ite8258ChassisBackend,
)

__all__ = ["BACKEND_REGISTRATION", "Ite8258ChassisBackend"]
