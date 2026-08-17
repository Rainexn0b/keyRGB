"""Dormant scaffold for the speculative ITE 8233 lightbar backend."""

from __future__ import annotations

from src.core.backends.base import (
    BackendMetadata,
    BackendRegistration,
    BackendStability,
    ExperimentalEvidence,
)

from .backend import Ite8233Backend

BACKEND_REGISTRATION = BackendRegistration(
    metadata=BackendMetadata(
        name="ite8233_none_chassis_lightbar_clevo",
        priority=96,
        provider="usb-userspace",
        stability=BackendStability.EXPERIMENTAL,
        experimental_evidence=ExperimentalEvidence.REVERSE_ENGINEERED,
    ),
    factory=Ite8233Backend,
)

__all__ = ["BACKEND_REGISTRATION", "Ite8233Backend"]
