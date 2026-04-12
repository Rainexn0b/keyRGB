from __future__ import annotations

import logging
from typing import Any

from src.core.backends.registry import select_backend
from src.core.resources.defaults import REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS
from src.core.utils.logging_utils import log_throttled


logger = logging.getLogger(__name__)
_PERKEY_HARDWARE_RUNTIME_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _select_backend() -> Any:
    """Select a keyboard backend (env `KEYRGB_BACKEND` or auto)."""

    try:
        return select_backend()
    except _PERKEY_HARDWARE_RUNTIME_ERRORS as exc:  # @quality-exception exception-transparency: backend registry selection involves runtime hardware probing and must degrade to None on recoverable runtime failures
        log_throttled(
            logger,
            "perkey.hardware.select_backend.failed",
            interval_s=60,
            level=logging.DEBUG,
            msg="Failed to select backend; disabling perkey hardware",
            exc=exc,
        )
        return None


def _backend_dimensions_or_reference(backend: object) -> tuple[int, int]:
    if backend is None:
        return REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS

    try:
        num_rows, num_cols = backend.dimensions()
        return int(num_rows), int(num_cols)
    except _PERKEY_HARDWARE_RUNTIME_ERRORS:  # @quality-exception exception-transparency: keyboard dimension read falls back to the reference matrix on recoverable backend failures
        return REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS


_backend = _select_backend()
NUM_ROWS, NUM_COLS = _backend_dimensions_or_reference(_backend)


def get_keyboard():
    """Return a keyboard instance if the backend is available."""

    if _backend is None:
        return None
    try:
        return _backend.get_device()
    except _PERKEY_HARDWARE_RUNTIME_ERRORS as exc:  # @quality-exception exception-transparency: USB device open is a runtime hardware boundary and recoverable failures must degrade to None
        log_throttled(
            logger,
            "perkey.hardware.get_keyboard",
            interval_s=60,
            level=logging.DEBUG,
            msg="Failed to open keyboard device; perkey hardware unavailable",
            exc=exc,
        )
        return None
