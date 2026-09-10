"""Single-instance identity for the Uniform Color window (UX-09).

Owns the ``uniform-<route>`` lock-name resolution so ``uniform.py`` stays
small. The caller passes its (monkeypatchable) route-resolution callables;
environment fallback semantics match GUI construction.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable

from keyrgb.core.secondary_device_routes import SecondaryDeviceRoute

logger = logging.getLogger(__name__)


def uniform_instance_identity(
    *,
    target_context: str | None = None,
    requested_backend: str | None = None,
    resolve_secondary_route_fn: Callable[..., SecondaryDeviceRoute | None],
    route_for_backend_name_fn: Callable[..., SecondaryDeviceRoute | None],
    route_for_device_type_fn: Callable[..., SecondaryDeviceRoute | None],
) -> str:
    """Return the UX-09 single-instance identity for the Uniform Color window.

    ``uniform-keyboard`` names the primary keyboard target, otherwise
    ``uniform-<route.state_key>`` with underscores normalized to hyphens.
    ``None`` arguments fall back to ``KEYRGB_UNIFORM_TARGET_CONTEXT`` /
    ``KEYRGB_UNIFORM_BACKEND``, mirroring GUI construction.
    """

    raw_context = (
        target_context if target_context is not None else os.environ.get("KEYRGB_UNIFORM_TARGET_CONTEXT", "keyboard")
    )
    raw_backend = requested_backend if requested_backend is not None else os.environ.get("KEYRGB_UNIFORM_BACKEND", "")
    route = resolve_secondary_route_fn(
        target_context=str(raw_context or "keyboard"),
        requested_backend=str(raw_backend or ""),
        route_for_backend_name_fn=route_for_backend_name_fn,
        route_for_device_type_fn=route_for_device_type_fn,
    )
    if route is None:
        return "uniform-keyboard"
    return f"uniform-{str(route.state_key).strip().lower().replace('_', '-')}"
