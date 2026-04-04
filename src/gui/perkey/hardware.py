from __future__ import annotations

import logging
from typing import Any

from src.core.backends.registry import select_backend
from src.core.resources.defaults import REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS
from src.core.utils.logging_utils import log_throttled


logger = logging.getLogger(__name__)


def _select_backend() -> Any:
    """Select a keyboard backend (env `KEYRGB_BACKEND` or auto)."""

    try:
        return select_backend()
    except Exception as exc:  # @quality-exception exception-transparency: backend registry selection involves runtime hardware probing and must degrade to None when unavailable
        log_throttled(
            logger,
            "perkey.hardware.select_backend.failed",
            interval_s=60,
            level=logging.DEBUG,
            msg="Failed to select backend; disabling perkey hardware",
            exc=exc,
        )
        return None


_backend = _select_backend()

try:
    if _backend is None:
        raise RuntimeError("No backend")
    NUM_ROWS, NUM_COLS = _backend.dimensions()
    NUM_ROWS, NUM_COLS = int(NUM_ROWS), int(NUM_COLS)
except Exception:  # @quality-exception exception-transparency: keyboard dimension read at import time falls back to reference matrix; backend may be unavailable
    NUM_ROWS, NUM_COLS = REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS


def get_keyboard():
    """Return a keyboard instance if the backend is available."""

    if _backend is None:
        return None
    try:
        return _backend.get_device()
    except Exception as exc:  # @quality-exception exception-transparency: USB device open is a runtime hardware boundary and failures must degrade to None
        log_throttled(
            logger,
            "perkey.hardware.get_keyboard",
            interval_s=60,
            level=logging.DEBUG,
            msg="Failed to open keyboard device; perkey hardware unavailable",
            exc=exc,
        )
        return None
