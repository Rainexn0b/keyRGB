#!/usr/bin/env python3
"""Boundary helpers for config polling - exception tuples, logging, recoverable runtime seams."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TypeVar

from src.tray.protocols import ConfigPollingTrayProtocol


logger = logging.getLogger(__name__)

_T = TypeVar("_T")

_CONFIG_POLLING_RUNTIME_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_TRAY_LOG_WRITE_EXCEPTIONS = (OSError, RuntimeError, ValueError)
_ENGINE_ATTR_SYNC_EXCEPTIONS = (LookupError, OSError, RuntimeError, TypeError, ValueError)
_ENABLE_USER_MODE_SAVE_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, ValueError)
_CONFIG_PERSIST_SYNC_EXCEPTIONS = (LookupError, OSError, RuntimeError, TypeError, ValueError)


def _log_module_exception(msg: str, exc: Exception) -> None:
    logger.error(msg, exc, exc_info=(type(exc), exc, exc.__traceback__))


def _run_recoverable_boundary(
    action: Callable[[], _T],
    *,
    runtime_exceptions: tuple[type[Exception], ...],
    on_recoverable: Callable[[Exception], _T],
) -> _T:
    try:
        return action()
    except runtime_exceptions as exc:  # @quality-exception exception-transparency: diagnostic-only helper callbacks and best-effort tray logger writes must contain recoverable runtime failures while unexpected defects still propagate
        return on_recoverable(exc)


def _log_tray_exception(
    tray: ConfigPollingTrayProtocol,
    msg: str,
    exc: Exception,
    *,
    log_module_exception_fn: Callable[[str, Exception], None] = _log_module_exception,
    run_recoverable_boundary_fn: Callable[..., None] = _run_recoverable_boundary,
) -> None:
    def _recover_logger_write(log_exc: Exception) -> None:
        log_module_exception_fn("Config polling tray exception logger failed: %s", log_exc)
        log_module_exception_fn(msg, exc)

    run_recoverable_boundary_fn(
        lambda: tray._log_exception(msg, exc),
        runtime_exceptions=_TRAY_LOG_WRITE_EXCEPTIONS,
        on_recoverable=_recover_logger_write,
    )


def _run_diagnostic_boundary(
    tray: ConfigPollingTrayProtocol,
    action: Callable[[], _T],
    *,
    error_msg: str,
    default: _T | None = None,
    runtime_exceptions: tuple[type[Exception], ...] = _CONFIG_POLLING_RUNTIME_EXCEPTIONS,
    log_tray_exception_fn: Callable[[ConfigPollingTrayProtocol, str, Exception], None] = _log_tray_exception,
    run_recoverable_boundary_fn: Callable[..., _T | None] = _run_recoverable_boundary,
) -> _T | None:
    def _recover_boundary(exc: Exception) -> _T | None:
        log_tray_exception_fn(tray, error_msg, exc)
        return default

    return run_recoverable_boundary_fn(
        action,
        runtime_exceptions=runtime_exceptions,
        on_recoverable=_recover_boundary,
    )
