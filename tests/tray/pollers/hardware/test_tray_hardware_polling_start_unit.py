from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


class _FakeThread:
    def __init__(self, *, target, daemon: bool):
        self.target = target
        self.daemon = daemon
        self.started = False

    def start(self):
        self.started = True


def test_start_hardware_polling_creates_daemon_thread_and_loop_runs_once(
    monkeypatch,
) -> None:
    import keyrgb.tray.pollers.hardware_polling as hp

    created = {}

    def fake_thread(*, target, daemon: bool):
        t = _FakeThread(target=target, daemon=daemon)
        created["t"] = t
        return t

    monkeypatch.setattr(hp.threading, "Thread", fake_thread)

    calls = {"apply": 0}

    def fake_apply(*_a, **_kw):
        calls["apply"] += 1
        return (1, False)

    monkeypatch.setattr(hp, "_apply_polled_hardware_state", fake_apply)

    # Stop after the first loop iteration.
    monkeypatch.setattr(hp.time, "sleep", lambda _s: (_ for _ in ()).throw(KeyboardInterrupt()))

    class _Lock:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    tray = SimpleNamespace(
        engine=SimpleNamespace(
            kb_lock=_Lock(),
            kb=SimpleNamespace(get_brightness=lambda: 5, is_off=lambda: False),
        )
    )

    hp.start_hardware_polling(tray)

    t = created["t"]
    assert t.daemon is True

    with pytest.raises(KeyboardInterrupt):
        t.target()

    assert calls["apply"] == 1


def test_stale_hardware_observation_is_rejected_after_newer_transition(monkeypatch) -> None:
    import keyrgb.tray.pollers.hardware_polling as hp
    from keyrgb.tray.controllers.runtime_coordination import run_tray_transition
    from keyrgb.tray.controllers.runtime_coordinator import TrayRuntimeCoordinator

    coordinator = TrayRuntimeCoordinator()
    tray = SimpleNamespace(runtime_coordinator=coordinator)
    apply = MagicMock(return_value=(0, True))
    monkeypatch.setattr(hp, "_apply_polled_hardware_state", apply)

    try:
        stale_revision = coordinator.capture_revision()
        run_tray_transition(tray, lambda: None)
        result = hp._apply_hardware_observation_if_current(
            tray,
            stale_revision,
            tray,
            raw_brightness=0,
            current_brightness=0,
            current_off=True,
            last_brightness=25,
            last_off_state=False,
        )
    finally:
        assert coordinator.stop_and_drain(timeout_s=1.0) is True

    assert result is None
    apply.assert_not_called()


def test_start_hardware_polling_exception_path_calls_handler(monkeypatch) -> None:
    import keyrgb.tray.pollers.hardware_polling as hp

    created = {}

    def fake_thread(*, target, daemon: bool):
        t = _FakeThread(target=target, daemon=daemon)
        created["t"] = t
        return t

    monkeypatch.setattr(hp.threading, "Thread", fake_thread)

    calls = {"handled": 0}

    def fake_handle(_tray, _exc, *, last_error_at: float):
        calls["handled"] += 1
        return last_error_at

    monkeypatch.setattr(hp, "_handle_hardware_polling_exception", fake_handle)

    # Stop after the exception branch completes.
    monkeypatch.setattr(hp.time, "sleep", lambda _s: (_ for _ in ()).throw(KeyboardInterrupt()))

    class _Lock:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    tray = SimpleNamespace(
        engine=SimpleNamespace(
            kb_lock=_Lock(),
            kb=SimpleNamespace(get_brightness=lambda: (_ for _ in ()).throw(RuntimeError("boom"))),
        )
    )

    hp.start_hardware_polling(tray)

    t = created["t"]
    with pytest.raises(KeyboardInterrupt):
        t.target()

    assert calls["handled"] == 1


def test_start_hardware_polling_uses_fast_poll_interval_after_power_source_transition(monkeypatch) -> None:
    import keyrgb.tray.pollers.hardware_polling as hp

    created = {}

    def fake_thread(*, target, daemon: bool):
        t = _FakeThread(target=target, daemon=daemon)
        created["t"] = t
        return t

    monkeypatch.setattr(hp.threading, "Thread", fake_thread)
    monkeypatch.setattr(hp, "_apply_polled_hardware_state", lambda *_a, **_kw: (1, False))

    sleep_calls: list[float] = []

    def fake_sleep(seconds: float):
        sleep_calls.append(float(seconds))
        raise KeyboardInterrupt()

    monkeypatch.setattr(hp.time, "sleep", fake_sleep)
    monkeypatch.setattr(hp.time, "monotonic", lambda: 101.0)

    class _Lock:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    tray = SimpleNamespace(
        _last_power_source_transition_at=100.0,
        engine=SimpleNamespace(
            kb_lock=_Lock(),
            kb=SimpleNamespace(get_brightness=lambda: 5, is_off=lambda: False),
        ),
    )

    hp.start_hardware_polling(tray)

    t = created["t"]
    with pytest.raises(KeyboardInterrupt):
        t.target()

    assert sleep_calls == [0.25]


def test_start_hardware_polling_propagates_unexpected_loop_errors(monkeypatch) -> None:
    import keyrgb.tray.pollers.hardware_polling as hp

    created = {}

    def fake_thread(*, target, daemon: bool):
        t = _FakeThread(target=target, daemon=daemon)
        created["t"] = t
        return t

    monkeypatch.setattr(hp.threading, "Thread", fake_thread)

    calls = {"handled": 0}

    def fake_handle(_tray, _exc, *, last_error_at: float):
        calls["handled"] += 1
        return last_error_at

    monkeypatch.setattr(hp, "_handle_hardware_polling_exception", fake_handle)

    class _Lock:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    tray = SimpleNamespace(
        engine=SimpleNamespace(
            kb_lock=_Lock(),
            kb=SimpleNamespace(get_brightness=lambda: (_ for _ in ()).throw(AssertionError("unexpected poll bug"))),
        )
    )

    hp.start_hardware_polling(tray)

    t = created["t"]
    with pytest.raises(AssertionError, match="unexpected poll bug"):
        t.target()

    assert calls["handled"] == 0
