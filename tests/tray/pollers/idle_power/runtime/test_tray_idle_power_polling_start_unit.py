from __future__ import annotations

from types import SimpleNamespace

import pytest


class _FakeThread:
    def __init__(self, *, target, daemon: bool):
        self.target = target
        self.daemon = daemon

    def start(self):
        return None


def test_start_idle_power_polling_thread_wiring_and_one_iteration(monkeypatch) -> None:
    import keyrgb.tray.pollers.idle_power.polling as ipp

    created = {}
    input_tracker = SimpleNamespace(closed=False)
    input_tracker.seconds_since_activity = lambda: None
    input_tracker.close = lambda: setattr(input_tracker, "closed", True)

    def fake_thread(*, target, daemon: bool):
        t = _FakeThread(target=target, daemon=daemon)
        created["t"] = t
        return t

    monkeypatch.setattr(ipp.threading, "Thread", fake_thread)

    # Avoid connecting to the real Wayland compositor during unit tests.
    monkeypatch.setattr(ipp, "_create_wayland_idle_tracker", lambda _timeout_ms: None)
    monkeypatch.setattr(ipp, "_create_input_idle_tracker", lambda: input_tracker)

    # Force dimmed True and screen_off False.
    monkeypatch.setattr(ipp, "_read_dimmed_state", lambda _tray: True)
    monkeypatch.setattr(ipp, "_read_screen_off_state_drm", lambda: False)
    monkeypatch.setattr(ipp, "_get_session_id", lambda: None)

    # Make compute action stable and observable.
    monkeypatch.setattr(ipp, "_compute_idle_action", lambda **_kw: "turn_off")

    applied = {"n": 0}

    def fake_apply(_tray, *, action, dim_temp_brightness: int):
        assert action == "turn_off"
        applied["n"] += 1

    monkeypatch.setattr(ipp, "_apply_idle_action", fake_apply)

    sleep_calls: list[float] = []

    # Stop after the first loop.
    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(float(seconds))
        raise KeyboardInterrupt()

    monkeypatch.setattr(ipp.time, "sleep", fake_sleep)

    events = {"n": 0}

    tray = SimpleNamespace(
        config=SimpleNamespace(
            reload=lambda: None,
            power_management_enabled=True,
            brightness=10,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="off",
            screen_dim_temp_brightness=5,
        ),
        is_off=False,
        _log_event=lambda *_a, **_kw: events.__setitem__("n", events["n"] + 1),
        engine=SimpleNamespace(),
    )

    ipp.start_idle_power_polling(tray, ite_num_rows=6, ite_num_cols=21, idle_timeout_s=60.0)

    t = created["t"]
    assert t.daemon is True

    with pytest.raises(KeyboardInterrupt):
        t.target()

    assert applied["n"] == 1
    assert events["n"] == 1
    assert sleep_calls == [0.5]
    assert input_tracker.closed is True


def test_start_idle_power_polling_suppresses_dim_sync_for_asusctl_backend(monkeypatch) -> None:
    import keyrgb.tray.pollers.idle_power.polling as ipp

    created = {}

    def fake_thread(*, target, daemon: bool):
        t = _FakeThread(target=target, daemon=daemon)
        created["t"] = t
        return t

    monkeypatch.setattr(ipp.threading, "Thread", fake_thread)

    # Avoid connecting to the real Wayland compositor during unit tests.
    monkeypatch.setattr(ipp, "_create_wayland_idle_tracker", lambda _timeout_ms: None)

    monkeypatch.setattr(ipp, "_read_dimmed_state", lambda _tray: True)
    monkeypatch.setattr(ipp, "_read_screen_off_state_drm", lambda: False)
    monkeypatch.setattr(ipp, "_get_session_id", lambda: None)

    def assert_dim_sync_suppressed(**kw):
        # Config requests screen-dim sync, but asusctl backend should suppress it by default.
        assert kw["screen_dim_sync_enabled"] is False
        return "none"

    monkeypatch.setattr(ipp, "_compute_idle_action", assert_dim_sync_suppressed)
    monkeypatch.setattr(ipp, "_apply_idle_action", lambda *_a, **_kw: None)
    sleep_calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(float(seconds))
        raise KeyboardInterrupt()

    monkeypatch.setattr(ipp.time, "sleep", fake_sleep)

    tray = SimpleNamespace(
        backend=SimpleNamespace(name="asusctl-aura"),
        config=SimpleNamespace(
            reload=lambda: None,
            power_management_enabled=True,
            brightness=10,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="off",
            screen_dim_temp_brightness=5,
        ),
        is_off=False,
        _log_event=lambda *_a, **_kw: None,
        engine=SimpleNamespace(),
    )

    ipp.start_idle_power_polling(tray, ite_num_rows=6, ite_num_cols=21, idle_timeout_s=60.0)

    with pytest.raises(KeyboardInterrupt):
        created["t"].target()

    assert sleep_calls == [0.5]


def test_start_idle_power_polling_allows_dim_sync_for_asusctl_with_env_override(monkeypatch) -> None:
    import keyrgb.tray.pollers.idle_power.polling as ipp

    monkeypatch.setenv("KEYRGB_ALLOW_DIM_SYNC_ASUSCTL", "1")

    created = {}

    def fake_thread(*, target, daemon: bool):
        t = _FakeThread(target=target, daemon=daemon)
        created["t"] = t
        return t

    monkeypatch.setattr(ipp.threading, "Thread", fake_thread)

    # Avoid connecting to the real Wayland compositor during unit tests.
    monkeypatch.setattr(ipp, "_create_wayland_idle_tracker", lambda _timeout_ms: None)

    monkeypatch.setattr(ipp, "_read_dimmed_state", lambda _tray: True)
    monkeypatch.setattr(ipp, "_read_screen_off_state_drm", lambda: False)
    monkeypatch.setattr(ipp, "_get_session_id", lambda: None)

    def assert_dim_sync_allowed(**kw):
        assert kw["screen_dim_sync_enabled"] is True
        return "none"

    monkeypatch.setattr(ipp, "_compute_idle_action", assert_dim_sync_allowed)
    monkeypatch.setattr(ipp, "_apply_idle_action", lambda *_a, **_kw: None)
    sleep_calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(float(seconds))
        raise KeyboardInterrupt()

    monkeypatch.setattr(ipp.time, "sleep", fake_sleep)

    tray = SimpleNamespace(
        backend=SimpleNamespace(name="asusctl-aura"),
        config=SimpleNamespace(
            reload=lambda: None,
            power_management_enabled=True,
            brightness=10,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="off",
            screen_dim_temp_brightness=5,
        ),
        is_off=False,
        _log_event=lambda *_a, **_kw: None,
        engine=SimpleNamespace(),
    )

    ipp.start_idle_power_polling(tray, ite_num_rows=6, ite_num_cols=21, idle_timeout_s=60.0)

    with pytest.raises(KeyboardInterrupt):
        created["t"].target()


def test_effective_screen_dim_sync_enabled_logs_event_failures(monkeypatch) -> None:
    import keyrgb.tray.pollers.idle_power.polling as ipp

    logged: list[tuple[str, Exception]] = []

    tray = SimpleNamespace(
        backend=SimpleNamespace(name="asusctl-aura"),
        _dim_sync_suppressed_logged=False,
        _log_event=lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("event boom")),
        _log_exception=lambda msg, exc: logged.append((msg, exc)),
    )

    assert ipp._effective_screen_dim_sync_enabled(tray, True) is False
    assert tray._dim_sync_suppressed_logged is True
    assert len(logged) == 1
    assert logged[0][0] == "Idle power event logging failed: %s"
    assert isinstance(logged[0][1], RuntimeError)
    assert str(logged[0][1]) == "event boom"


def test_effective_screen_dim_sync_enabled_propagates_unexpected_event_failures() -> None:
    import keyrgb.tray.pollers.idle_power.polling as ipp

    tray = SimpleNamespace(
        backend=SimpleNamespace(name="asusctl-aura"),
        _dim_sync_suppressed_logged=False,
        _log_event=lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("unexpected event bug")),
        _log_exception=lambda *_a, **_kw: None,
    )

    with pytest.raises(AssertionError, match="unexpected event bug"):
        ipp._effective_screen_dim_sync_enabled(tray, True)


def test_start_idle_power_polling_logs_loop_errors_with_module_fallback(monkeypatch) -> None:
    import keyrgb.tray.pollers.idle_power.polling as ipp

    created = {}
    module_logs: list[tuple[str, Exception]] = []
    run_calls = {"count": 0}
    sleep_calls: list[float] = []

    def fake_thread(*, target, daemon: bool):
        t = _FakeThread(target=target, daemon=daemon)
        created["t"] = t
        return t

    def fake_iteration(*_args, **_kwargs):
        run_calls["count"] += 1
        if run_calls["count"] == 1:
            raise RuntimeError("loop boom")

    monkeypatch.setattr(ipp.threading, "Thread", fake_thread)
    monkeypatch.setattr(ipp, "run_idle_power_iteration", fake_iteration)
    monkeypatch.setattr(ipp, "_get_session_id", lambda: None)
    monkeypatch.setattr(ipp, "_log_module_exception", lambda msg, exc: module_logs.append((msg, exc)))
    monkeypatch.setattr(ipp.time, "monotonic", lambda: 31.0)

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(float(seconds))
        raise KeyboardInterrupt()

    monkeypatch.setattr(ipp.time, "sleep", fake_sleep)

    tray = SimpleNamespace(
        config=SimpleNamespace(),
        _log_exception=lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("logger boom")),
    )

    ipp.start_idle_power_polling(tray, ite_num_rows=6, ite_num_cols=21, idle_timeout_s=60.0)

    with pytest.raises(KeyboardInterrupt):
        created["t"].target()

    assert run_calls["count"] == 1
    assert sleep_calls == [0.5]
    assert [entry[0] for entry in module_logs] == [
        "Idle power tray exception logger failed: %s",
        "Idle power polling error: %s",
    ]
    assert isinstance(module_logs[0][1], RuntimeError)
    assert str(module_logs[0][1]) == "logger boom"
    assert isinstance(module_logs[1][1], RuntimeError)
    assert str(module_logs[1][1]) == "loop boom"


def test_start_idle_power_polling_propagates_unexpected_logger_failures(monkeypatch) -> None:
    import keyrgb.tray.pollers.idle_power.polling as ipp

    created = {}
    run_calls = {"count": 0}
    sleep_calls: list[float] = []

    def fake_thread(*, target, daemon: bool):
        t = _FakeThread(target=target, daemon=daemon)
        created["t"] = t
        return t

    def fake_iteration(*_args, **_kwargs):
        run_calls["count"] += 1
        if run_calls["count"] == 1:
            raise RuntimeError("loop boom")

    monkeypatch.setattr(ipp.threading, "Thread", fake_thread)
    monkeypatch.setattr(ipp, "run_idle_power_iteration", fake_iteration)
    monkeypatch.setattr(ipp, "_get_session_id", lambda: None)
    monkeypatch.setattr(ipp.time, "monotonic", lambda: 31.0)

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(float(seconds))
        raise KeyboardInterrupt()

    monkeypatch.setattr(ipp.time, "sleep", fake_sleep)

    tray = SimpleNamespace(
        config=SimpleNamespace(),
        _log_exception=lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("unexpected logger bug")),
    )

    ipp.start_idle_power_polling(tray, ite_num_rows=6, ite_num_cols=21, idle_timeout_s=60.0)

    with pytest.raises(AssertionError, match="unexpected logger bug"):
        created["t"].target()


def test_start_idle_power_polling_propagates_unexpected_loop_errors(monkeypatch) -> None:
    import keyrgb.tray.pollers.idle_power.polling as ipp

    created = {}
    run_calls = {"count": 0}

    def fake_thread(*, target, daemon: bool):
        t = _FakeThread(target=target, daemon=daemon)
        created["t"] = t
        return t

    def fake_iteration(*_args, **_kwargs):
        run_calls["count"] += 1
        raise AssertionError("unexpected idle loop bug")

    monkeypatch.setattr(ipp.threading, "Thread", fake_thread)
    monkeypatch.setattr(ipp, "run_idle_power_iteration", fake_iteration)
    monkeypatch.setattr(ipp, "_get_session_id", lambda: None)

    tray = SimpleNamespace(
        config=SimpleNamespace(),
        _log_exception=lambda *_a, **_kw: None,
    )

    ipp.start_idle_power_polling(tray, ite_num_rows=6, ite_num_cols=21, idle_timeout_s=60.0)

    with pytest.raises(AssertionError, match="unexpected idle loop bug"):
        created["t"].target()

    assert run_calls["count"] == 1
