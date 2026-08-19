from __future__ import annotations

from keyrgb.core.backends.base import (
    BackendMetadata,
    BackendRegistration,
    BackendRole,
    BackendStability,
    ExperimentalEvidence,
)

from .backend import SysfsMouseBackend
from .device import SysfsMouseDevice

BACKEND_REGISTRATION = BackendRegistration(
    metadata=BackendMetadata(
        name="sysfs-mouse",
        priority=10,
        role=BackendRole.AUXILIARY,
        provider="kernel-sysfs",
        stability=BackendStability.EXPERIMENTAL,
        experimental_evidence=ExperimentalEvidence.SPECULATIVE,
    ),
    factory=SysfsMouseBackend,
)

__all__ = ["BACKEND_REGISTRATION", "SysfsMouseBackend", "SysfsMouseDevice"]
