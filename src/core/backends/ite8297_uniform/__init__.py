"""Experimental ITE 8297 uniform-color HID backend."""

from __future__ import annotations

from src.core.backends.base import (
    BackendMetadata,
    BackendRegistration,
    BackendStability,
    ExperimentalEvidence,
)

from .backend import Ite8297Backend

BACKEND_REGISTRATION = BackendRegistration(
    metadata=BackendMetadata(
        name="ite8297_uniform",
        priority=95,
        provider="usb-userspace",
        stability=BackendStability.EXPERIMENTAL,
        experimental_evidence=ExperimentalEvidence.REVERSE_ENGINEERED,
    ),
    factory=Ite8297Backend,
)

__all__ = ["BACKEND_REGISTRATION", "Ite8297Backend"]
