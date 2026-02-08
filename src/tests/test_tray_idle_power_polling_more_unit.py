from __future__ import annotations

from types import SimpleNamespace

import pytest


class _FakeThread:
    def __init__(self, *, target, daemon: bool):
        self.target = target
        self.daemon = daemon

    def start(self):
        return None


def test_ensure_idle_state_sets_defaults() -> None:
    from src.tray.pollers.idle_power_polling import _ensure_idle_state

    tray = SimpleNamespace()
    _ensure_idle_state(tray)

    assert tray._idle_forced_off is False
    assert tray._user_forced_off is False
    assert tray._power_forced_off is False
    assert tray._dim_backlight_baselines == {}
    assert tray._dim_temp_active is False
    assert tray._dim_temp_target_brightness is None


def test_read_logind_idle_seconds_parsing_and_monotonic(monkeypatch) -> None:
    import src.tray.pollers.idle_power_polling as ipp

    # Active idle: now_us(2_000_000) - idle_since_us(1_000_000) = 1s
    monkeypatch.setattr(ipp.time, "monotonic", lambda: 2.0)

    monkeypatch.setattr(
        ipp,
        "_run",
        lambda _argv, timeout_s=1.0: "IdleHint=yes\nIdleSinceHintMonotonic=1000000\n",
    )

    assert ipp._read_logind_idle_seconds(session_id="1") == pytest.approx(1.0)

    # Not idle -> 0.0
    monkeypatch.setattr(
        ipp,
        "_run",
        lambda _argv, timeout_s=1.0: "IdleHint=no\nIdleSinceHintMonotonic=123\n",
    )
    assert ipp._read_logind_idle_seconds(session_id="1") == 0.0

    # Unknown IdleHint -> None
    monkeypatch.setattr(
        ipp,
        "_run",
        lambda _argv, timeout_s=1.0: "IdleHint=maybe\nIdleSinceHintMonotonic=123\n",
    )
    assert ipp._read_logind_idle_seconds(session_id="1") is None

    # Missing IdleHint -> None
    monkeypatch.setattr(
        ipp,
        "_run",
        lambda _argv, timeout_s=1.0: "IdleSinceHintMonotonic=123\n",
    )
    assert ipp._read_logind_idle_seconds(session_id="1") is None

    # None output -> None
    monkeypatch.setattr(ipp, "_run", lambda _argv, timeout_s=1.0: None)
    assert ipp._read_logind_idle_seconds(session_id="1") is None


def test_restore_from_idle_best_effort_and_log_swallow(monkeypatch) -> None:
    import src.tray.pollers.idle_power_polling as ipp

    calls = {"start": 0, "refresh": 0, "log": 0}

    tray = SimpleNamespace(
        is_off=True,
        _idle_forced_off=True,
        _last_brightness=33,
        config=SimpleNamespace(brightness=0),
        engine=SimpleNamespace(current_color=(12, 34, 56)),
        _log_exception=None,
        _start_current_effect=None,
        _refresh_ui=None,
    )

    def boom_start():
        calls["start"] += 1
        assert tray.engine.current_color == (0, 0, 0)
        raise RuntimeError("boom")

    def boom_log(*_a, **_kw):
        calls["log"] += 1
        raise RuntimeError("boom")

    tray._start_current_effect = boom_start
    tray._log_exception = boom_log
    tray._refresh_ui = lambda: calls.__setitem__("refresh", calls["refresh"] + 1)

    ipp._restore_from_idle(tray)

    assert tray.is_off is False
    assert tray._idle_forced_off is False
    assert tray.config.brightness == 33
    assert calls["start"] == 1
    assert calls["log"] == 1
    assert calls["refresh"] == 1


def test_apply_idle_action_dim_to_temp_respects_is_off_and_sw_effect(
    monkeypatch,
) -> None:
    import src.tray.pollers.idle_power_polling as ipp

    engine_calls = {"n": 0, "apply_to_hardware": None}

    def set_brightness(v: int, *, apply_to_hardware: bool):
        engine_calls["n"] += 1
        engine_calls["apply_to_hardware"] = apply_to_hardware

    tray = SimpleNamespace(
        is_off=False,
        config=SimpleNamespace(effect="perkey"),
        engine=SimpleNamespace(set_brightness=set_brightness),
    )

    ipp._apply_idle_action(tray, action="dim_to_temp", dim_temp_brightness=5)

    assert tray._dim_temp_active is True
    assert tray._dim_temp_target_brightness == 5
    assert engine_calls["n"] == 1
    # perkey is a hardware per-key apply path -> DO apply to hardware
    assert engine_calls["apply_to_hardware"] is True

    tray_sw = SimpleNamespace(
        is_off=False,
        config=SimpleNamespace(effect="rainbow_wave"),
        engine=SimpleNamespace(set_brightness=set_brightness),
        _dim_temp_active=False,
        _dim_temp_target_brightness=None,
    )
    ipp._apply_idle_action(tray_sw, action="dim_to_temp", dim_temp_brightness=5)
    assert engine_calls["n"] == 2
    assert engine_calls["apply_to_hardware"] is False

    tray2 = SimpleNamespace(
        is_off=True,
        config=SimpleNamespace(effect="uniform"),
        engine=SimpleNamespace(set_brightness=set_brightness),
        _dim_temp_active=False,
        _dim_temp_target_brightness=None,
    )

    ipp._apply_idle_action(tray2, action="dim_to_temp", dim_temp_brightness=5)
    assert engine_calls["n"] == 2  # unchanged; skipped when off


def test_apply_idle_action_restore_branch_gated_by_forced_off(monkeypatch) -> None:
    import src.tray.pollers.idle_power_polling as ipp

    called = {"n": 0}

    monkeypatch.setattr(
        ipp,
        "_restore_from_idle",
        lambda _tray: called.__setitem__("n", called["n"] + 1),
    )

    tray = SimpleNamespace(_user_forced_off=True, _power_forced_off=False)
    ipp._apply_idle_action(tray, action="restore", dim_temp_brightness=5)
    assert called["n"] == 0

    tray2 = SimpleNamespace(_user_forced_off=False, _power_forced_off=True)
    ipp._apply_idle_action(tray2, action="restore", dim_temp_brightness=5)
    assert called["n"] == 0

    tray3 = SimpleNamespace(_user_forced_off=False, _power_forced_off=False, config=SimpleNamespace())
    ipp._apply_idle_action(tray3, action="restore", dim_temp_brightness=5)
    assert called["n"] == 1


def test_start_idle_power_polling_thread_wiring_and_one_iteration(monkeypatch) -> None:
    import src.tray.pollers.idle_power_polling as ipp

    created = {}

    def fake_thread(*, target, daemon: bool):
        t = _FakeThread(target=target, daemon=daemon)
        created["t"] = t
        return t

    monkeypatch.setattr(ipp.threading, "Thread", fake_thread)

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

    # Stop after the first loop.
    monkeypatch.setattr(ipp.time, "sleep", lambda _s: (_ for _ in ()).throw(KeyboardInterrupt()))

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


def test_start_idle_power_polling_suppresses_dim_sync_for_asusctl_backend(monkeypatch) -> None:
    import src.tray.pollers.idle_power_polling as ipp

    created = {}

    def fake_thread(*, target, daemon: bool):
        t = _FakeThread(target=target, daemon=daemon)
        created["t"] = t
        return t

    monkeypatch.setattr(ipp.threading, "Thread", fake_thread)

    monkeypatch.setattr(ipp, "_read_dimmed_state", lambda _tray: True)
    monkeypatch.setattr(ipp, "_read_screen_off_state_drm", lambda: False)
    monkeypatch.setattr(ipp, "_get_session_id", lambda: None)

    def assert_dim_sync_suppressed(**kw):
        # Config requests screen-dim sync, but asusctl backend should suppress it by default.
        assert kw["screen_dim_sync_enabled"] is False
        return "none"

    monkeypatch.setattr(ipp, "_compute_idle_action", assert_dim_sync_suppressed)
    monkeypatch.setattr(ipp, "_apply_idle_action", lambda *_a, **_kw: None)
    monkeypatch.setattr(ipp.time, "sleep", lambda _s: (_ for _ in ()).throw(KeyboardInterrupt()))

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


def test_start_idle_power_polling_allows_dim_sync_for_asusctl_with_env_override(monkeypatch) -> None:
    import src.tray.pollers.idle_power_polling as ipp

    monkeypatch.setenv("KEYRGB_ALLOW_DIM_SYNC_ASUSCTL", "1")

    created = {}

    def fake_thread(*, target, daemon: bool):
        t = _FakeThread(target=target, daemon=daemon)
        created["t"] = t
        return t

    monkeypatch.setattr(ipp.threading, "Thread", fake_thread)

    monkeypatch.setattr(ipp, "_read_dimmed_state", lambda _tray: True)
    monkeypatch.setattr(ipp, "_read_screen_off_state_drm", lambda: False)
    monkeypatch.setattr(ipp, "_get_session_id", lambda: None)

    def assert_dim_sync_allowed(**kw):
        assert kw["screen_dim_sync_enabled"] is True
        return "none"

    monkeypatch.setattr(ipp, "_compute_idle_action", assert_dim_sync_allowed)
    monkeypatch.setattr(ipp, "_apply_idle_action", lambda *_a, **_kw: None)
    monkeypatch.setattr(ipp.time, "sleep", lambda _s: (_ for _ in ()).throw(KeyboardInterrupt()))

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
