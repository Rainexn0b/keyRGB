from __future__ import annotations

import logging
from collections.abc import Callable
from threading import Thread
from typing import Final, Protocol, SupportsIndex, SupportsInt, cast

logger = logging.getLogger("src.core.effects.engine_start")

_ThreadGenerationValue = str | bytes | bytearray | SupportsInt | SupportsIndex

_THREAD_JOIN_CLEANUP_ERRORS: Final[tuple[type[Exception], ...]] = (
    AttributeError,
    RuntimeError,
    TypeError,
    ValueError,
)
_PERMISSION_CALLBACK_RUNTIME_ERRORS: Final[tuple[type[Exception], ...]] = (
    AttributeError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_DEVICE_UNAVAILABLE_MARK_RUNTIME_ERRORS: Final[tuple[type[Exception], ...]] = (
    AttributeError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


class _ThreadOwner(Protocol):
    thread: Thread | None


class _ThreadGenerationOwner(Protocol):
    _thread_generation: _ThreadGenerationValue


class _PermissionErrorCallbackOwner(Protocol):
    _permission_error_cb: Callable[[Exception], None] | None


class _ManagedEffectThread(Thread):
    """Thread wrapper that clears the published engine thread after join."""

    def __init__(self, *, engine: _ThreadOwner, target: Callable[[], None]) -> None:
        super().__init__(target=target, daemon=True)
        self._engine = engine

    def join(self, timeout: float | None = None) -> None:
        super().join(timeout=timeout)
        if self.is_alive():
            return
        _run_engine_support_best_effort(
            lambda: setattr(self._engine, "thread", None) if self._engine.thread is self else None,
            runtime_errors=_THREAD_JOIN_CLEANUP_ERRORS,
        )


def _sw_effect_method(engine: object, method_name: str) -> Callable[[], None]:
    return cast(Callable[[], None], getattr(engine, method_name))


def _thread_generation_or_default(engine: object, *, default: int) -> int:
    try:
        thread_owner = cast(_ThreadGenerationOwner, engine)
        return int(thread_owner._thread_generation)
    except AttributeError:
        return default


def _permission_error_callback_or_none(engine: object) -> Callable[[Exception], None] | None:
    try:
        callback_owner = cast(_PermissionErrorCallbackOwner, engine)
        return callback_owner._permission_error_cb
    except AttributeError:
        return None


def _mark_device_unavailable_callback_or_none(engine: object) -> Callable[[], None] | None:
    try:
        callback = getattr(engine, "mark_device_unavailable")
    except AttributeError:
        return None
    return cast(Callable[[], None] | None, callback if callable(callback) else None)


def _run_engine_support_best_effort(
    action: Callable[[], None],
    *,
    runtime_errors: tuple[type[Exception], ...],
    log_message: str | None = None,
) -> None:
    try:
        action()
    except runtime_errors:  # @quality-exception exception-transparency: shared engine-support cleanup and callback boundaries must contain recoverable runtime failures while preserving unexpected defects
        if log_message is not None:
            logger.exception(log_message)


def _notify_permission_error_callback_best_effort(engine: object, exc: Exception) -> None:
    callback = _permission_error_callback_or_none(engine)
    if not callable(callback):
        return
    _run_engine_support_best_effort(
        lambda: callback(exc),
        runtime_errors=_PERMISSION_CALLBACK_RUNTIME_ERRORS,
        log_message="Permission error callback failed",
    )


def _mark_device_unavailable_best_effort(engine: object) -> None:
    mark = _mark_device_unavailable_callback_or_none(engine)
    if not callable(mark):
        return
    _run_engine_support_best_effort(
        mark,
        runtime_errors=_DEVICE_UNAVAILABLE_MARK_RUNTIME_ERRORS,
        log_message="Failed to mark keyboard device unavailable after disconnect",
    )
