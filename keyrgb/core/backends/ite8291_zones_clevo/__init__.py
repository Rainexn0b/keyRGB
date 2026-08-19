"""Experimental 4-zone backend for the legacy ITE 8291 ce00 firmware path."""

from __future__ import annotations

from keyrgb.core.backends.base import (
    BackendMetadata,
    BackendRegistration,
    BackendStability,
    ExperimentalEvidence,
)

from .backend import Ite8291ZonesBackend

BACKEND_REGISTRATION = BackendRegistration(
    metadata=BackendMetadata(
        name="ite8291_zones_clevo",
        priority=96,
        provider="usb-userspace",
        stability=BackendStability.EXPERIMENTAL,
        experimental_evidence=ExperimentalEvidence.REVERSE_ENGINEERED,
    ),
    factory=Ite8291ZonesBackend,
)

__all__ = ["BACKEND_REGISTRATION", "Ite8291ZonesBackend"]
