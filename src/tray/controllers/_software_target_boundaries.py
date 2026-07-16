"""Recoverable runtime boundaries for software-target controller seams."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol, TypeVar, cast

logger = logging.getLogger(__name__)
_ResultT = TypeVar("_ResultT")

_ENGINE_ATTR_WRITE_EXCEPTIONS = (OSError, OverflowError, RuntimeError, TypeError, ValueError)
_CONFIG_ATTR_WRITE_EXCEPTIONS = (OSError, RuntimeError, TypeError, ValueError)
# Best-effort tray log/event callbacks (no map LookupError expected).
_TRAY_CALLBACK_RUNTIME_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


class _SoftwareTargetTrayProtocol(Protocol):
    @property
    def config(self) -> object: ...

    @property
    def engine(self) -> object: ...

    @property
    def is_off(self) -> bool: ...

    def _log_exception(self, msg: str, exc: Exception) -> None: ...

    def _log_event(self, source: str, action: str, **fields: object) -> None: ...


class _PermissionIssueTrayProtocol(Protocol):
    def _notify_permission_issue(self, exc: Exception) -> None: ...


def run_recoverable_boundary(
    action: Callable[[], _ResultT],
    *,
    runtime_exceptions: tuple[type[Exception], ...],
    on_recoverable: Callable[[Exception], None],
    fallback: _ResultT,
    reraise_recoverable: bool = False,
) -> _ResultT:
    try:
        return action()
    except runtime_exceptions as exc:  # @quality-exception exception-transparency: shared secondary-target device and tray callback runtime seams must either invalidate cached state or degrade to fallback logging while unexpected defects still propagate
        on_recoverable(exc)
        if reraise_recoverable:
            raise
        return fallback


def try_log_event(tray: _SoftwareTargetTrayProtocol, source: str, action: str, **fields: object) -> None:
    call_tray_callback_best_effort(
        lambda: tray._log_event(source, action, **fields),
        on_recoverable=lambda exc: logger.exception("Tray event logging failed: %s", exc),
    )


def call_tray_callback_best_effort(
    action: Callable[[], None],
    *,
    on_recoverable: Callable[[Exception], None],
) -> bool:
    def _call_action() -> bool:
        action()
        return True

    return run_recoverable_boundary(
        _call_action,
        runtime_exceptions=_TRAY_CALLBACK_RUNTIME_EXCEPTIONS,
        on_recoverable=on_recoverable,
        fallback=False,
    )


def notify_permission_issue_or_none(tray: _SoftwareTargetTrayProtocol) -> Callable[[Exception], None] | None:
    try:
        notify_permission_issue = cast(_PermissionIssueTrayProtocol, tray)._notify_permission_issue
    except AttributeError:
        return None
    if not callable(notify_permission_issue):
        return None
    return notify_permission_issue


def set_engine_attr_best_effort(tray: _SoftwareTargetTrayProtocol, attr: str, value: object, *, error_msg: str) -> None:
    engine = getattr(tray, "engine", None)
    if engine is None:
        return

    try:
        setattr(engine, attr, value)
    except AttributeError:
        return
    except _ENGINE_ATTR_WRITE_EXCEPTIONS as exc:
        log_boundary_exception(tray, error_msg, exc)


def set_config_attr_best_effort(tray: _SoftwareTargetTrayProtocol, attr: str, value: object, *, error_msg: str) -> None:
    config = getattr(tray, "config", None)
    if config is None:
        return

    try:
        setattr(config, attr, value)
    except AttributeError:
        return
    except _CONFIG_ATTR_WRITE_EXCEPTIONS as exc:
        log_boundary_exception(tray, error_msg, exc)


def log_boundary_exception(tray: _SoftwareTargetTrayProtocol, msg: str, exc: Exception) -> None:
    if call_tray_callback_best_effort(
        lambda: tray._log_exception(msg, exc),
        on_recoverable=lambda log_exc: logger.exception(
            "Tray exception logger failed while logging boundary: %s", log_exc
        ),
    ):
        return

    logger.error(msg, exc, exc_info=(type(exc), exc, exc.__traceback__))
