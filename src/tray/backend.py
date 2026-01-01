"""Tray-facing backend helpers.

The tray uses backend selection to gate UI features and to optionally probe
hardware capabilities. This module keeps that logic out of the tray
application constructor.
"""

from __future__ import annotations

from typing import Any

from src.core.backends.registry import select_backend


def select_backend_with_introspection() -> tuple[Any, Any, Any]:
    """Select a backend and best-effort introspect its probe/capabilities.

    Returns `(backend, backend_probe, backend_caps)`; any item may be `None`.
    This function must be resilient: tray startup should never fail here.
    """

    backend = select_backend()

    backend_probe = None
    try:
        probe_fn = getattr(backend, "probe", None) if backend is not None else None
        if callable(probe_fn):
            backend_probe = probe_fn()
    except Exception:
        backend_probe = None

    backend_caps = None
    try:
        backend_caps = backend.capabilities() if backend is not None else None
    except Exception:
        backend_caps = None

    return backend, backend_probe, backend_caps
