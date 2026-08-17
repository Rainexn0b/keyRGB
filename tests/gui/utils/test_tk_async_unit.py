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


class _ImmediateRoot:
    def after(self, delay_ms: int, callback) -> None:
        callback()


def test_run_in_thread_swallows_closed_root_callback_schedule_error() -> None:
    root = _ClosedRoot()
    results: list[str] = []

    job = tk_async.run_in_thread(root, lambda: "done", results.append)

    assert root.failed_schedule.wait(1.0)
    assert results == []
    assert job.generation == 1


def test_run_in_thread_swallows_closed_root_delayed_start_error() -> None:
    class _DelayClosedRoot:
        def after(self, delay_ms: int, callback) -> None:
            raise RuntimeError("main thread is not in main loop")

    job = tk_async.run_in_thread(_DelayClosedRoot(), lambda: "done", lambda _result: None, delay_ms=100)
    assert job.cancelled is False


def test_run_in_thread_cancel_suppresses_on_done() -> None:
    started = Event()
    release = Event()
    results: list[str] = []

    def work() -> str:
        started.set()
        assert release.wait(1.0)
        return "late"

    job = tk_async.run_in_thread(_ImmediateRoot(), work, results.append)
    assert started.wait(1.0)
    job.cancel()
    release.set()
    assert job.cancelled is True
    assert results == []


def test_coordinator_delivers_only_latest_generation() -> None:
    coordinator = tk_async.TkAsyncCoordinator()
    results: list[str] = []
    first_started = Event()
    first_release = Event()

    def first_work() -> str:
        first_started.set()
        assert first_release.wait(1.0)
        return "old"

    first = coordinator.submit(_ImmediateRoot(), first_work, results.append)
    assert first_started.wait(1.0)
    second = coordinator.submit(_ImmediateRoot(), lambda: "new", results.append)
    first_release.set()

    assert first.cancelled is True
    assert second.generation == 2
    assert results == ["new"]


def test_submit_gui_work_stays_synchronous_without_coordinator() -> None:
    results: list[int] = []
    job = tk_async.submit_gui_work(object(), None, lambda: 7, results.append)
    assert job is None
    assert results == [7]
