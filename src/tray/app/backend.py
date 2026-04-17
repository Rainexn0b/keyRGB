"""Tray-facing backend helpers.

The tray uses backend selection to gate UI features and to optionally probe
hardware capabilities. This module keeps that logic out of the tray
application constructor.
"""

from __future__ import annotations

from collections.abc import Callable

import logging

from ._startup import _run_best_effort
from src.core.backends.base import KeyboardBackend
from src.core.backends.registry import select_backend
from src.core.diagnostics.device_discovery import collect_device_discovery
from src.core.resources.defaults import REFERENCE_MATRIX_COLS, REFERENCE_MATRIX_ROWS


_TRAY_BACKEND_RUNTIME_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _log_debug_boundary(*, logger: logging.Logger, message: str) -> Callable[[Exception], None]:
    def _log(exc: Exception) -> None:
        logger.log(logging.DEBUG, message, exc_info=(type(exc), exc, exc.__traceback__))

    return _log


def load_ite_dimensions() -> tuple[int, int]:
    """Load keyboard matrix dimensions from the active backend.

    Falls back to the reference default if anything goes wrong.
    """

    logger = logging.getLogger(__name__)

    def _load_dimensions() -> tuple[int, int]:
        backend = select_backend()
        if backend is None:
            return REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS
        r, c = backend.dimensions()
        return int(r), int(c)

    return _run_best_effort(
        _load_dimensions,
        fallback=(REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS),
        recoverable_errors=_TRAY_BACKEND_RUNTIME_ERRORS,
        on_recoverable=_log_debug_boundary(
            logger=logger,
            message="Falling back to default keyboard dimensions",
        ),
    )


def select_backend_with_introspection() -> tuple[KeyboardBackend | None, object | None, object | None]:
    """Select a backend and best-effort introspect its probe/capabilities.

    Returns `(backend, backend_probe, backend_caps)`; any item may be `None`.
    This function must be resilient: tray startup should never fail here.
    """

    logger = logging.getLogger(__name__)
    backend = select_backend()

    def _load_probe() -> object | None:
        probe_fn = getattr(backend, "probe", None) if backend is not None else None
        if callable(probe_fn):
            return probe_fn()
        return None

    backend_probe = _run_best_effort(
        _load_probe,
        fallback=None,
        recoverable_errors=_TRAY_BACKEND_RUNTIME_ERRORS,
        on_recoverable=_log_debug_boundary(
            logger=logger,
            message="Backend probe failed during tray introspection",
        ),
    )

    backend_caps = _run_best_effort(
        lambda: backend.capabilities() if backend is not None else None,
        fallback=None,
        recoverable_errors=_TRAY_BACKEND_RUNTIME_ERRORS,
        on_recoverable=_log_debug_boundary(
            logger=logger,
            message="Backend capabilities lookup failed during tray introspection",
        ),
    )

    return backend, backend_probe, backend_caps


def select_device_discovery_snapshot() -> dict[str, object] | None:
    """Collect a best-effort device discovery snapshot for tray status lines.

    This must stay non-fatal: tray startup should continue even if diagnostics
    helpers are unavailable or the scan raises.
    """

    logger = logging.getLogger(__name__)

    payload = _run_best_effort(
        lambda: collect_device_discovery(include_usb=True),
        fallback=None,
        recoverable_errors=_TRAY_BACKEND_RUNTIME_ERRORS,
        on_recoverable=_log_debug_boundary(
            logger=logger,
            message="Tray device discovery snapshot collection failed",
        ),
    )

    return payload if isinstance(payload, dict) else None
