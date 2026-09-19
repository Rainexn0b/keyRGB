from __future__ import annotations

import json
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


def _backend_dimensions_or_reference(backend: KeyboardBackend | None) -> tuple[int, int]:
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
_PERKEY_PREFLIGHT_ENV = "KEYRGB_PERKEY_PREFLIGHT"


def _tray_managed_config_only() -> bool:
    return os.environ.get(_TRAY_MANAGED_GUI_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _tray_preflight_payload() -> dict[str, object]:
    """Parse the tray-launched ``KEYRGB_PERKEY_PREFLIGHT`` payload (fails closed)."""

    raw = os.environ.get(_PERKEY_PREFLIGHT_ENV, "")
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _tray_preflight_declares_per_key() -> bool:
    return bool(_tray_preflight_payload().get("per_key"))


def _tray_preflight_declares_zoned() -> bool:
    return bool(_tray_preflight_payload().get("zoned"))


def _backend_supports_zoned(backend: KeyboardBackend | None) -> bool:
    if backend is None:
        return False
    return _recover_runtime_boundary(
        lambda: normalize_backend_capabilities(backend.capabilities()).zoned,
        fallback=False,
        log_key="perkey.hardware.zoned_capabilities",
        log_msg="Backend lacks zoned capability evidence; treating as non-zoned",
    )


def backend_supports_per_key() -> bool:
    """Return True when the active backend (or tray preflight) supports per-key lighting."""

    if _tray_managed_config_only():
        return _tray_preflight_declares_per_key()
    return _backend_supports_per_key(_backend)


def backend_supports_zoned() -> bool:
    """Return True when the active backend (or tray preflight) is zoned, not per-key."""

    if backend_supports_per_key():
        return False
    if _tray_managed_config_only():
        return _tray_preflight_declares_zoned()
    return _backend_supports_zoned(_backend)


def backend_zone_count() -> int:
    """Hardware zone count for zoned editors; 0 when not in zone-paint mode."""

    if not backend_supports_zoned():
        return 0
    if _tray_managed_config_only():
        raw_dimensions = _tray_preflight_payload().get("dimensions")
        try:
            rows, cols = raw_dimensions  # type: ignore[misc]
            return max(1, int(rows) * int(cols))
        except (TypeError, ValueError):
            return 4
    rows, cols = _backend_dimensions_or_reference(_backend)
    return max(1, int(rows) * int(cols))


_backend = None if _tray_managed_config_only() else _select_backend()
NUM_ROWS, NUM_COLS = (
    _backend_dimensions_or_reference(_backend)
    if _backend_supports_per_key(_backend)
    else (REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS)
)


def get_keyboard() -> KeyboardDevice | None:
    """Return a keyboard instance if the backend is available."""

    if _tray_managed_config_only() or _backend is None:
        return None
    if not (_backend_supports_per_key(_backend) or _backend_supports_zoned(_backend)):
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
