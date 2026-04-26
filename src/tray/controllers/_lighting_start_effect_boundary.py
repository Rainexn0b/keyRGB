from __future__ import annotations

import logging
from collections.abc import Callable

from src.tray.protocols import LightingTrayProtocol


logger = logging.getLogger(__name__)

_LOCAL_COMPATIBILITY_FALLBACK_EXCEPTIONS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


def handle_start_current_effect_exception(
    tray: LightingTrayProtocol,
    exc: Exception,
    *,
    is_device_disconnected_fn: Callable[[Exception], bool],
    is_permission_denied_fn: Callable[[Exception], bool],
    log_boundary_exception_fn: Callable[[LightingTrayProtocol, str, Exception], None],
) -> None:
    """Map recoverable start_current_effect failures to best-effort tray actions."""

    if is_device_disconnected_fn(exc):
        try:
            tray.engine.mark_device_unavailable()
        except _LOCAL_COMPATIBILITY_FALLBACK_EXCEPTIONS as mark_exc:
            log_boundary_exception_fn(tray, "Failed to mark device unavailable: %s", mark_exc)
        logger.warning("Keyboard device unavailable: %s", exc)
        return

    if is_permission_denied_fn(exc):
        try:
            tray._notify_permission_issue(exc)
        except _LOCAL_COMPATIBILITY_FALLBACK_EXCEPTIONS as notify_exc:
            log_boundary_exception_fn(tray, "Failed to notify permission issue: %s", notify_exc)
        return

    log_boundary_exception_fn(tray, "Error starting effect: %s", exc)
