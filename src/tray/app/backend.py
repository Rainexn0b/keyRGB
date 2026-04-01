"""Tray-facing backend helpers.

The tray uses backend selection to gate UI features and to optionally probe
hardware capabilities. This module keeps that logic out of the tray
application constructor.
"""

from __future__ import annotations

from typing import Any

import logging

from src.core.diagnostics.device_discovery import collect_device_discovery
from src.core.backends.registry import select_backend
from src.core.resources.defaults import REFERENCE_MATRIX_COLS, REFERENCE_MATRIX_ROWS


def load_ite_dimensions() -> tuple[int, int]:
    """Load keyboard matrix dimensions from the active backend.

    Falls back to the reference default if anything goes wrong.
    """

    logger = logging.getLogger(__name__)

    try:
        backend = select_backend()
        if backend is None:
            return REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS
        r, c = backend.dimensions()
        return int(r), int(c)
    except Exception:
        logger.log(logging.DEBUG, "Falling back to default keyboard dimensions", exc_info=True)
        return REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS


def select_backend_with_introspection() -> tuple[Any, Any, Any]:
    """Select a backend and best-effort introspect its probe/capabilities.

    Returns `(backend, backend_probe, backend_caps)`; any item may be `None`.
    This function must be resilient: tray startup should never fail here.
    """

    logger = logging.getLogger(__name__)
    backend = select_backend()

    backend_probe = None
    try:
        probe_fn = getattr(backend, "probe", None) if backend is not None else None
        if callable(probe_fn):
            backend_probe = probe_fn()
    except Exception:
        logger.log(logging.DEBUG, "Backend probe failed during tray introspection", exc_info=True)
        backend_probe = None

    backend_caps = None
    try:
        backend_caps = backend.capabilities() if backend is not None else None
    except Exception:
        logger.log(logging.DEBUG, "Backend capabilities lookup failed during tray introspection", exc_info=True)
        backend_caps = None

    return backend, backend_probe, backend_caps


def select_device_discovery_snapshot() -> dict[str, Any] | None:
    """Collect a best-effort device discovery snapshot for tray status lines.

    This must stay non-fatal: tray startup should continue even if diagnostics
    helpers are unavailable or the scan raises.
    """

    logger = logging.getLogger(__name__)

    try:
        payload = collect_device_discovery(include_usb=True)
    except Exception:
        logger.log(logging.DEBUG, "Tray device discovery snapshot collection failed", exc_info=True)
        return None

    return payload if isinstance(payload, dict) else None
