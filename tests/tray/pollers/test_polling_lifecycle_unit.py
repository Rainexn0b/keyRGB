from __future__ import annotations

from types import SimpleNamespace


class _Event:
    def __init__(self, calls: list[str], *, wait_result: bool = False) -> None:
        self.calls = calls
        self.wait_result = wait_result
        self.set_state = False

    def is_set(self) -> bool:
        return self.set_state

    def wait(self, timeout: float | None = None) -> bool:
        self.calls.append(f"wait:{timeout}")
        return self.wait_result

    def set(self) -> None:
        self.calls.append("set")
        self.set_state = True


def test_wait_for_shutdown_uses_event_wait_instead_of_fallback_sleep() -> None:
    from src.tray.pollers._lifecycle import wait_for_shutdown

    calls: list[str] = []
    event = _Event(calls, wait_result=True)
    tray = SimpleNamespace(_polling_shutdown_event=event)

    stopped = wait_for_shutdown(
        tray,
        1.25,
        sleep_fn=lambda _timeout: (_ for _ in ()).throw(AssertionError("fallback sleep must not run")),
    )

    assert stopped is True
    assert calls == ["wait:1.25"]


def test_wait_for_shutdown_falls_back_to_supplied_sleep_without_event() -> None:
    from src.tray.pollers._lifecycle import wait_for_shutdown

    sleeps: list[float] = []

    assert wait_for_shutdown(SimpleNamespace(), 0.75, sleep_fn=sleeps.append) is False
    assert sleeps == [0.75]


def test_shutdown_requested_reflects_registered_event() -> None:
    from src.tray.pollers._lifecycle import shutdown_requested

    calls: list[str] = []
    event = _Event(calls)
    tray = SimpleNamespace(_polling_shutdown_event=event)

    assert shutdown_requested(tray) is False
    event.set()
    assert shutdown_requested(tray) is True


def test_stop_all_polling_signals_before_joining_every_registered_thread() -> None:
    from src.tray.app.lifecycle import stop_all_polling

    calls: list[str] = []
    event = _Event(calls)
    threads = [
        SimpleNamespace(join=lambda *, timeout: calls.append(f"join:first:{timeout}"), is_alive=lambda: False),
        SimpleNamespace(join=lambda *, timeout: calls.append(f"join:second:{timeout}"), is_alive=lambda: False),
    ]
    tray = SimpleNamespace(_polling_shutdown_event=event, _polling_threads=threads)

    stop_all_polling(tray, join_timeout_s=0.5)

    assert calls == ["set", "join:first:0.5", "join:second:0.5"]
    assert threads == []


def test_stop_all_polling_continues_after_recoverable_join_error() -> None:
    from src.tray.app.lifecycle import stop_all_polling

    calls: list[str] = []

    def fail_join(*, timeout: float) -> None:
        calls.append(f"join:failed:{timeout}")
        raise RuntimeError("thread was not started")

    failed_thread = SimpleNamespace(join=fail_join)
    threads = [
        failed_thread,
        SimpleNamespace(join=lambda *, timeout: calls.append(f"join:later:{timeout}"), is_alive=lambda: False),
    ]
    tray = SimpleNamespace(_polling_shutdown_event=_Event(calls), _polling_threads=threads)

    quiesced = stop_all_polling(tray, join_timeout_s=0.25)

    assert calls == ["set", "join:failed:0.25", "join:later:0.25"]
    assert quiesced is False
    assert threads == [failed_thread]


def test_stop_all_polling_reports_and_retains_worker_still_alive_after_join() -> None:
    from src.tray.app.lifecycle import stop_all_polling

    calls: list[str] = []
    stopped = SimpleNamespace(
        join=lambda *, timeout: calls.append(f"join:stopped:{timeout}"),
        is_alive=lambda: calls.append("alive:stopped") or False,
    )
    stuck = SimpleNamespace(
        join=lambda *, timeout: calls.append(f"join:stuck:{timeout}"),
        is_alive=lambda: calls.append("alive:stuck") or True,
    )
    threads = [stopped, stuck]
    tray = SimpleNamespace(_polling_shutdown_event=_Event(calls), _polling_threads=threads)

    quiesced = stop_all_polling(tray, join_timeout_s=0.4)

    assert quiesced is False
    assert calls == [
        "set",
        "join:stopped:0.4",
        "alive:stopped",
        "join:stuck:0.4",
        "alive:stuck",
    ]
    assert threads == [stuck]


def test_stop_all_polling_retains_worker_without_liveness_probe() -> None:
    from src.tray.app.lifecycle import stop_all_polling

    worker = SimpleNamespace(join=lambda *, timeout: None)
    threads = [worker]
    tray = SimpleNamespace(_polling_shutdown_event=_Event([]), _polling_threads=threads)

    assert stop_all_polling(tray) is False
    assert threads == [worker]
