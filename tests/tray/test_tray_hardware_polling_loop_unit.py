from __future__ import annotations

from types import SimpleNamespace

import pytest


class _FakeThread:
    def __init__(self, *, target, daemon: bool):
        self.target = target
        self.daemon = daemon
        self.started = False

    def start(self):
        self.started = True


def test_normalize_brightness_invalid_returns_zero() -> None:
    from src.tray.pollers.hardware_polling import _normalize_brightness_to_config_scale

    assert _normalize_brightness_to_config_scale("nope") == 0  # type: ignore[arg-type]


def test_apply_polled_state_logs_brightness_change_but_swallows_log_errors(
    monkeypatch,
) -> None:
    from src.tray.pollers.hardware_polling import _apply_polled_hardware_state

    tray = SimpleNamespace(
        _dim_temp_active=False,
        _dim_temp_target_brightness=None,
        _power_forced_off=False,
        _user_forced_off=False,
        _idle_forced_off=False,
        _refresh_ui=lambda: None,
    )

    def boom(*_a, **_kw):
        raise RuntimeError("boom")

    tray._log_event = boom

    # last_brightness changes => tries to log; log throws; should still refresh and return.
    b, off = _apply_polled_hardware_state(
        tray,
        raw_brightness=None,
        current_brightness=10,
        current_off=False,
        last_brightness=5,
        last_off_state=None,
    )

    assert b == 10
    assert off is False


def test_apply_polled_state_dim_temp_target_bad_int_is_ignored(monkeypatch) -> None:
    from src.tray.pollers.hardware_polling import _apply_polled_hardware_state

    class BadInt:
        def __int__(self):
            raise TypeError("no")

    refreshed = {"n": 0}

    tray = SimpleNamespace(
        _dim_temp_active=True,
        _dim_temp_target_brightness=BadInt(),
        _power_forced_off=False,
        _user_forced_off=False,
        _idle_forced_off=False,
        _refresh_ui=lambda: refreshed.__setitem__("n", refreshed["n"] + 1),
        _log_event=None,
        is_off=False,
    )

    _apply_polled_hardware_state(
        tray,
        raw_brightness=7,
        current_brightness=7,
        current_off=False,
        last_brightness=9,
        last_off_state=None,
    )

    assert refreshed["n"] == 1


def test_apply_polled_state_off_state_change_branch_and_forced_off_gate() -> None:
    from src.tray.pollers.hardware_polling import _apply_polled_hardware_state

    refreshed = {"n": 0}

    tray = SimpleNamespace(
        _dim_temp_active=False,
        _dim_temp_target_brightness=None,
        _power_forced_off=True,
        _user_forced_off=False,
        _idle_forced_off=False,
        _refresh_ui=lambda: refreshed.__setitem__("n", refreshed["n"] + 1),
        _log_event=lambda *_a, **_kw: None,
        is_off=False,
    )

    # Off-state flips to True while power-forced-off => should return early with no UI refresh.
    b, off = _apply_polled_hardware_state(
        tray,
        raw_brightness=5,
        current_brightness=5,
        current_off=True,
        last_brightness=None,
        last_off_state=False,
    )

    assert (b, off) == (5, True)
    assert refreshed["n"] == 0


def test_start_hardware_polling_creates_daemon_thread_and_loop_runs_once(
    monkeypatch,
) -> None:
    import src.tray.pollers.hardware_polling as hp

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


def test_start_hardware_polling_exception_path_calls_handler(monkeypatch) -> None:
    import src.tray.pollers.hardware_polling as hp

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
