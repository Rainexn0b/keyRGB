from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Lock, Thread
from typing import Generic, TypeVar

T = TypeVar("T")
_TK_SCHEDULE_ERRORS = (RuntimeError, tk.TclError)


def _schedule_on_tk_thread(root: tk.Misc, callback: Callable[[], None], *, delay_ms: int = 0) -> bool:
    try:
        root.after(delay_ms, callback)
    except _TK_SCHEDULE_ERRORS:
        return False
    return True


@dataclass
class TkAsyncJob(Generic[T]):
    """One background GUI job with generation and cancel semantics."""

    generation: int
    _cancelled: bool = False
    _lock: Lock = field(default_factory=Lock, repr=False)

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True

    @property
    def cancelled(self) -> bool:
        with self._lock:
            return self._cancelled


class TkAsyncCoordinator:
    """Serialize GUI background jobs so only the latest result is delivered."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._generation = 0
        self._current: TkAsyncJob[object] | None = None

    def submit(
        self,
        root: tk.Misc,
        work: Callable[[], T],
        on_done: Callable[[T], None],
        *,
        delay_ms: int = 0,
    ) -> TkAsyncJob[T]:
        with self._lock:
            if self._current is not None:
                self._current.cancel()
            self._generation += 1
            job: TkAsyncJob[T] = TkAsyncJob(generation=self._generation)
            self._current = job  # type: ignore[assignment]
        _start_job(root, work, on_done, job, delay_ms=delay_ms)
        return job

    def cancel(self) -> None:
        with self._lock:
            if self._current is not None:
                self._current.cancel()


def _start_job(
    root: tk.Misc,
    work: Callable[[], T],
    on_done: Callable[[T], None],
    job: TkAsyncJob[T],
    *,
    delay_ms: int,
) -> None:
    def deliver(result: T) -> None:
        if job.cancelled:
            return
        on_done(result)

    def worker() -> None:
        if job.cancelled:
            return
        result = work()
        if job.cancelled:
            return
        _schedule_on_tk_thread(root, lambda: deliver(result))

    if delay_ms and delay_ms > 0:
        _schedule_on_tk_thread(root, lambda: Thread(target=worker, daemon=True).start(), delay_ms=delay_ms)
    else:
        Thread(target=worker, daemon=True).start()


def run_in_thread(
    root: tk.Misc,
    work: Callable[[], T],
    on_done: Callable[[T], None],
    *,
    delay_ms: int = 0,
) -> TkAsyncJob[T]:
    """Run work in a daemon thread and call on_done(result) on Tk's thread.

    Returns a job handle. Cancelled or superseded jobs do not invoke ``on_done``.
    This is a tiny utility to keep Tkinter UIs responsive while doing blocking work.
    """

    job: TkAsyncJob[T] = TkAsyncJob(generation=1)
    _start_job(root, work, on_done, job, delay_ms=delay_ms)
    return job


def submit_gui_work(
    owner: object,
    root: object | None,
    work: Callable[[], T],
    on_done: Callable[[T], None],
    *,
    delay_ms: int = 0,
) -> TkAsyncJob[T] | None:
    """Submit work through ``owner.tk_jobs`` when a live Tk root is present.

    Unit tests that construct window objects without a coordinator keep the
    previous synchronous callback behavior.
    """

    coordinator = getattr(owner, "tk_jobs", None)
    if coordinator is None or root is None or not hasattr(root, "after"):
        on_done(work())
        return None
    return coordinator.submit(root, work, on_done, delay_ms=delay_ms)
