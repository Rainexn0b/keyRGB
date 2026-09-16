"""Isolated experimental auxiliary backend for the Tongfang ITE 8291 lightbar (048d:6005)."""

from __future__ import annotations

from keyrgb.core.backends.base import (
    BackendMetadata,
    BackendRegistration,
    BackendRole,
    BackendStability,
    ExperimentalEvidence,
)

from .backend import BACKEND_NAME, Ite8291TongfangLightbarBackend

BACKEND_REGISTRATION = BackendRegistration(
    metadata=BackendMetadata(
        name=BACKEND_NAME,
        priority=96,
        role=BackendRole.AUXILIARY,
        provider="usb-userspace",
        stability=BackendStability.EXPERIMENTAL,
        experimental_evidence=ExperimentalEvidence.REVERSE_ENGINEERED,
    ),
    factory=Ite8291TongfangLightbarBackend,
)

__all__ = ["BACKEND_NAME", "BACKEND_REGISTRATION", "Ite8291TongfangLightbarBackend"]
