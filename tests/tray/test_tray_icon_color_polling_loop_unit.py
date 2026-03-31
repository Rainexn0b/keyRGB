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


def test_normalize_color_hits_exception_path() -> None:
    from src.tray.pollers.icon_color_polling import _normalize_color

    # int(object()) raises TypeError -> should fall back via the broad except.
    assert _normalize_color((object(), 2, 3)) == (0, 0, 0)


def test_compute_icon_sig_speed_and_brightness_bad_int_fall_back_to_zero() -> None:
    from src.tray.pollers import icon_color_polling as icp

    tray = SimpleNamespace(
        is_off=False,
        config=SimpleNamespace(effect="perkey", speed=object(), brightness=object(), color=(1, 2, 3)),
    )

    sig = icp._compute_icon_sig(tray)
    assert sig[2] == 0
    assert sig[3] == 0


def test_start_icon_color_polling_starts_daemon_thread(monkeypatch) -> None:
    import src.tray.pollers.icon_color_polling as icp

    created = {}

    def fake_thread(*, target, daemon: bool):
        t = _FakeThread(target=target, daemon=daemon)
        created["t"] = t
        return t

    monkeypatch.setattr(icp.threading, "Thread", fake_thread)

    tray = SimpleNamespace(_update_icon=lambda: None, _log_exception=lambda *_a, **_kw: None)

    icp.start_icon_color_polling(tray)
    assert created["t"].daemon is True


def test_icon_color_polling_loop_logs_then_exits_on_log_exception(monkeypatch) -> None:
    import src.tray.pollers.icon_color_polling as icp

    created = {}

    def fake_thread(*, target, daemon: bool):
        t = _FakeThread(target=target, daemon=daemon)
        created["t"] = t
        return t

    monkeypatch.setattr(icp.threading, "Thread", fake_thread)

    # Force update path, then trigger an exception and a log-exception that causes return.
    monkeypatch.setattr(icp, "_compute_icon_sig", lambda _tray: (False, "rainbow", 1, 1, (0, 0, 0)))
    monkeypatch.setattr(icp, "_should_update_icon", lambda _sig, _last: True)
    monkeypatch.setattr(icp.time, "monotonic", lambda: 100.0)

    tray = SimpleNamespace(
        _update_icon=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        _log_exception=lambda *_a, **_kw: (_ for _ in ()).throw(OSError("nope")),
    )

    icp.start_icon_color_polling(tray)

    # The loop should return naturally (no sleep needed) when _log_exception raises OSError.
    created["t"].target()


def test_icon_color_polling_loop_updates_once(monkeypatch) -> None:
    import src.tray.pollers.icon_color_polling as icp

    created = {}

    def fake_thread(*, target, daemon: bool):
        t = _FakeThread(target=target, daemon=daemon)
        created["t"] = t
        return t

    monkeypatch.setattr(icp.threading, "Thread", fake_thread)

    monkeypatch.setattr(icp, "_compute_icon_sig", lambda _tray: (False, "perkey", 1, 1, (0, 0, 0)))
    monkeypatch.setattr(icp, "_should_update_icon", lambda _sig, _last: True)

    # Stop after one iteration.
    monkeypatch.setattr(icp.time, "sleep", lambda _s: (_ for _ in ()).throw(KeyboardInterrupt()))

    calls = {"n": 0}

    tray = SimpleNamespace(
        _update_icon=lambda: calls.__setitem__("n", calls["n"] + 1),
        _log_exception=lambda *_a, **_kw: None,
    )

    icp.start_icon_color_polling(tray)

    with pytest.raises(KeyboardInterrupt):
        created["t"].target()

    assert calls["n"] == 1
