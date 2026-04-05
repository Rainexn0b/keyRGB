from __future__ import annotations

from threading import Event

from src.gui.utils import tk_async


class _ClosedRoot:
    def __init__(self) -> None:
        self.calls: list[int] = []
        self.failed_schedule = Event()

    def after(self, delay_ms: int, callback) -> None:
        self.calls.append(delay_ms)
        if delay_ms == 0:
            self.failed_schedule.set()
            raise RuntimeError("main thread is not in main loop")
        callback()


def test_run_in_thread_swallows_closed_root_callback_schedule_error() -> None:
    root = _ClosedRoot()
    results: list[str] = []

    tk_async.run_in_thread(root, lambda: "done", results.append)

    assert root.failed_schedule.wait(1.0)
    assert results == []


def test_run_in_thread_swallows_closed_root_delayed_start_error() -> None:
    class _DelayClosedRoot:
        def after(self, delay_ms: int, callback) -> None:
            raise RuntimeError("main thread is not in main loop")

    tk_async.run_in_thread(_DelayClosedRoot(), lambda: "done", lambda _result: None, delay_ms=100)