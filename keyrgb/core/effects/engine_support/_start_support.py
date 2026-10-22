from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from concurrent.futures import Future
from contextlib import contextmanager
from threading import RLock, Thread, current_thread, get_ident
from time import monotonic
from typing import Final, Protocol, SupportsIndex, SupportsInt, cast

logger = logging.getLogger("keyrgb.core.effects.engine_start")

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


class DeferredFadeJobs:
    """Start token-owned fade workers after the serialized engine leaf exits."""

    kb_lock: RLock
    _closed: bool = False
    _fade_workers: set[Thread] | None = None
    _deferred_fade_jobs: list[tuple[Future[bool], Callable[[], bool]]] | None = None
    _deferred_fade_owner: int | None = None
    _invalidate_brightness_fade: Callable[[], int]

    @contextmanager
    def defer_brightness_fades(self) -> Iterator[list[Future[bool]]]:
        jobs: list[tuple[Future[bool], Callable[[], bool]]] = []
        self._deferred_fade_jobs = jobs
        self._deferred_fade_owner = get_ident()
        pending: list[Future[bool]] = []
        prepared = False
        try:
            yield pending
            prepared = True
        finally:
            self._deferred_fade_jobs = None
            self._deferred_fade_owner = None
            if not prepared:
                self._invalidate_brightness_fade()
                for future, _ in jobs:
                    future.set_result(False)
                jobs.clear()
            for future, action in jobs:
                pending.append(future)
                self._start_fade_job(future, action)

    def _start_fade_job(self, future: Future[bool], action: Callable[[], bool]) -> None:
        started = False
        try:
            # Publish/start atomically with close; completion callbacks never run
            # under kb_lock because they may re-enter the tray coordinator.
            with self.kb_lock:
                if not self._closed:
                    if self._fade_workers is None:
                        self._fade_workers = set()
                    worker = Thread(
                        target=self._run_fade_job, args=(future, action), name="keyrgb-brightness-fade", daemon=True
                    )
                    worker.start()
                    self._fade_workers.add(worker)
                    started = True
        finally:
            if not started:
                future.set_result(False)

    def _run_fade_job(self, future: Future[bool], action: Callable[[], bool]) -> None:
        try:
            try:
                result = action()
            except Exception as exc:  # @quality-exception exception-transparency: worker exceptions are logged and delivered to the restore completion future
                logger.exception("Deferred brightness operation failed")
                future.set_exception(exc)
            else:
                future.set_result(result)
        finally:
            with self.kb_lock:
                if self._fade_workers is not None:
                    self._fade_workers.discard(current_thread())

    def _drain_brightness_fades(self, timeout_s: float) -> bool:
        """Join published fades outside engine locks, sharing one time budget."""
        deadline = monotonic() + max(0.0, timeout_s)
        with self.kb_lock:
            workers = tuple(self._fade_workers or ())
        for worker in workers:
            if worker is not current_thread():
                worker.join(timeout=max(0.0, deadline - monotonic()))
        return not any(worker.is_alive() for worker in workers)


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
        callback = getattr(engine, "mark_device_unavailable")  # noqa: B009 - engine is intentionally duck-typed
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
