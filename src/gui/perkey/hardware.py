from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TypeVar

from src.core.backends.base import KeyboardBackend, KeyboardDevice
from src.core.resources.defaults import REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS
from src.gui._backend_runtime import select_backend
from src.core.utils.logging_utils import log_throttled


logger = logging.getLogger(__name__)
_T = TypeVar("_T")
_PERKEY_HARDWARE_RUNTIME_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _recover_runtime_boundary(
    operation: Callable[[], _T],
    *,
    fallback: _T,
    log_key: str | None = None,
    log_msg: str | None = None,
) -> _T:
    try:
        return operation()
    except _PERKEY_HARDWARE_RUNTIME_ERRORS as exc:  # @quality-exception exception-transparency: per-key hardware runtime boundaries must degrade via a caller-provided fallback on recoverable backend and device failures while still propagating unexpected defects
        if log_key is not None and log_msg is not None:
            log_throttled(
                logger,
                log_key,
                interval_s=60,
                level=logging.DEBUG,
                msg=log_msg,
                exc=exc,
            )
        return fallback


def _select_backend() -> KeyboardBackend | None:
    """Select a keyboard backend (env `KEYRGB_BACKEND` or auto)."""

    return _recover_runtime_boundary(
        select_backend,
        fallback=None,
        log_key="perkey.hardware.select_backend.failed",
        log_msg="Failed to select backend; disabling perkey hardware",
    )


def _coerce_backend_dimensions_pair(backend: KeyboardBackend) -> tuple[int, int]:
    rows, cols = backend.dimensions()
    return int(rows), int(cols)


def _backend_dimensions_or_reference(backend: object) -> tuple[int, int]:
    if backend is None:
        return REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS

    return _recover_runtime_boundary(
        lambda: _coerce_backend_dimensions_pair(backend),
        fallback=(REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS),
    )


_backend = _select_backend()
NUM_ROWS, NUM_COLS = _backend_dimensions_or_reference(_backend)


def get_keyboard() -> KeyboardDevice | None:
    """Return a keyboard instance if the backend is available."""

    if _backend is None:
        return None

    return _recover_runtime_boundary(
        _backend.get_device,
        fallback=None,
        log_key="perkey.hardware.get_keyboard",
        log_msg="Failed to open keyboard device; perkey hardware unavailable",
    )
