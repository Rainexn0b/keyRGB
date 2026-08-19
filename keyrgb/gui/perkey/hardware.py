from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import TypeVar

from keyrgb.core.backends.base import KeyboardBackend, KeyboardDevice, normalize_backend_capabilities
from keyrgb.core.backends.registry import select_backend
from keyrgb.core.resources.defaults import REFERENCE_MATRIX_COLS, REFERENCE_MATRIX_ROWS
from keyrgb.core.runtime.hardware_ownership import acquire_hardware_control_lock, release_hardware_control_lock
from keyrgb.core.utils.logging_utils import log_throttled

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


def _backend_supports_per_key(backend: KeyboardBackend | None) -> bool:
    if backend is None:
        return False
    return _recover_runtime_boundary(
        lambda: normalize_backend_capabilities(backend.capabilities()).per_key,
        fallback=False,
        log_key="perkey.hardware.capabilities",
        log_msg="Backend lacks per-key capability evidence; disabling perkey hardware",
    )


_TRAY_MANAGED_GUI_ENV = "KEYRGB_TRAY_MANAGED_GUI"


def _tray_managed_config_only() -> bool:
    return os.environ.get(_TRAY_MANAGED_GUI_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


_backend = None if _tray_managed_config_only() else _select_backend()
NUM_ROWS, NUM_COLS = (
    _backend_dimensions_or_reference(_backend)
    if _backend_supports_per_key(_backend)
    else (REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS)
)


def get_keyboard() -> KeyboardDevice | None:
    """Return a keyboard instance if the backend is available."""

    if _tray_managed_config_only() or _backend is None or not _backend_supports_per_key(_backend):
        return None
    if not acquire_hardware_control_lock():
        return None

    keyboard = _recover_runtime_boundary(
        _backend.get_device,
        fallback=None,
        log_key="perkey.hardware.get_keyboard",
        log_msg="Failed to open keyboard device; perkey hardware unavailable",
    )
    if keyboard is None:
        release_hardware_control_lock()
    return keyboard


def release_hardware_control() -> None:
    release_hardware_control_lock()
