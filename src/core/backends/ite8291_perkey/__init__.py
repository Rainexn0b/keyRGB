"""Experimental native HID backend for legacy ITE 8291 keyboards."""

from __future__ import annotations

from src.core.backends.base import (
    BackendMetadata,
    BackendRegistration,
    BackendStability,
    ExperimentalEvidence,
)

from .backend import Ite8291Backend

BACKEND_REGISTRATION = BackendRegistration(
    metadata=BackendMetadata(
        name="ite8291_perkey",
        priority=97,
        provider="usb-userspace",
        stability=BackendStability.EXPERIMENTAL,
        experimental_evidence=ExperimentalEvidence.REVERSE_ENGINEERED,
    ),
    factory=Ite8291Backend,
)

__all__ = ["BACKEND_REGISTRATION", "Ite8291Backend"]
