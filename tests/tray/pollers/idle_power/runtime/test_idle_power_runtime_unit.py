from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.tray.pollers.idle_power import _runtime


def _make_tray(*, reload_fn, log_event_fn):
    from tests.tray.fakes import make_owner_backed_simple_tray

    return make_owner_backed_simple_tray(
        config=SimpleNamespace(
            reload=reload_fn,
            power_management_enabled=True,
            brightness=25,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="off",
            screen_dim_temp_brightness=5,
        ),
        engine=SimpleNamespace(),
        backend=None,
        is_off=False,
        idle_forced_off=False,
        user_forced_off=False,
        power_forced_off=False,
        dim_temp_active=False,
        dim_temp_target_brightness=None,
        last_resume_at=0.0,
        _dim_sync_suppressed_logged=False,
        _log_event=log_event_fn,
    )


def test_log_idle_action_best_effort_swallows_log_event_failures() -> None:
    def fail_log_event(*_args, **_kwargs) -> None:
        raise RuntimeError("log failed")

    tray = _make_tray(reload_fn=lambda: None, log_event_fn=fail_log_event)

    _runtime._log_idle_action_best_effort(
        tray,
        action="turn_off",
        dimmed=False,
        screen_off=False,
        brightness=25,
        dim_sync_enabled=True,
        dim_sync_mode="off",
        dim_temp_brightness=5,
    )


def test_log_idle_action_best_effort_propagates_unexpected_log_event_failures() -> None:
    def fail_log_event(*_args, **_kwargs) -> None:
        raise AssertionError("unexpected log bug")

    tray = _make_tray(reload_fn=lambda: None, log_event_fn=fail_log_event)

    with pytest.raises(AssertionError, match="unexpected log bug"):
        _runtime._log_idle_action_best_effort(
            tray,
            action="turn_off",
            dimmed=False,
            screen_off=False,
            brightness=25,
            dim_sync_enabled=True,
            dim_sync_mode="off",
            dim_temp_brightness=5,
        )


def test_run_idle_power_iteration_continues_when_config_reload_fails() -> None:
    def fail_reload() -> None:
        raise RuntimeError("reload failed")

    applied: list[tuple[str | None, int]] = []
    tray = _make_tray(reload_fn=fail_reload, log_event_fn=lambda *_args, **_kwargs: None)

    _runtime.run_idle_power_iteration(
        tray,
        loop_state=_runtime.IdlePollLoopState(),
        idle_timeout_s=60.0,
        session_id=None,
        now_monotonic_fn=lambda: 1.0,
        ensure_idle_state_fn=lambda _tray: None,
        read_dimmed_state_fn=lambda _tray: False,
        read_screen_off_state_drm_fn=lambda: False,
        debounce_dim_and_screen_off_fn=lambda **kwargs: (
            kwargs["dimmed_raw"],
            kwargs["screen_off_raw"],
            kwargs["dimmed_true_streak"],
            kwargs["dimmed_false_streak"],
            kwargs["screen_off_true_streak"],
        ),
        read_logind_idle_seconds_fn=lambda **_kwargs: None,
        read_desktop_dim_timeout_fn=lambda _on_ac: None,
        create_wayland_idle_tracker_fn=lambda _timeout_ms: None,
        read_wayland_idle_fn=lambda _tracker: None,
        create_input_idle_tracker_fn=lambda: None,
        read_input_idle_seconds_fn=lambda _tracker: None,
        effective_screen_dim_sync_enabled_fn=lambda _tray, requested_enabled: requested_enabled,
        compute_idle_action_fn=lambda **_kwargs: "turn_off",
        build_idle_action_key_fn=lambda **_kwargs: "turn_off",
        should_log_idle_action_fn=lambda **_kwargs: False,
        apply_idle_action_fn=lambda _tray, *, action, dim_temp_brightness: applied.append(
            (action, dim_temp_brightness)
        ),
    )

    assert applied == [("turn_off", 5)]


def test_run_idle_power_iteration_suppresses_dim_sync_during_power_source_change() -> None:
    loop_state = _runtime.IdlePollLoopState(
        dimmed_true_streak=3,
        dimmed_false_streak=0,
        screen_off_true_streak=2,
        last_on_ac_power=True,
    )
    loop_state.backlight_state.baselines["panel"] = 100
    loop_state.backlight_state.dimmed["panel"] = True
    loop_state.backlight_state.screen_off = True

    applied: list[tuple[str | None, int]] = []
    tray = _make_tray(reload_fn=lambda: None, log_event_fn=lambda *_args, **_kwargs: None)

    _runtime.run_idle_power_iteration(
        tray,
        loop_state=loop_state,
        idle_timeout_s=60.0,
        session_id=None,
        now_monotonic_fn=lambda: 100.0,
        ensure_idle_state_fn=lambda _tray: None,
        read_dimmed_state_fn=lambda _state: True,
        read_screen_off_state_drm_fn=lambda: True,
        debounce_dim_and_screen_off_fn=lambda **kwargs: (
            kwargs["dimmed_raw"],
            kwargs["screen_off_raw"],
            kwargs["dimmed_true_streak"],
            kwargs["dimmed_false_streak"],
            kwargs["screen_off_true_streak"],
        ),
        read_logind_idle_seconds_fn=lambda **_kwargs: None,
        read_desktop_dim_timeout_fn=lambda _on_ac: None,
        create_wayland_idle_tracker_fn=lambda _timeout_ms: None,
        read_wayland_idle_fn=lambda _tracker: None,
        create_input_idle_tracker_fn=lambda: None,
        read_input_idle_seconds_fn=lambda _tracker: None,
        effective_screen_dim_sync_enabled_fn=lambda _tray, requested_enabled: requested_enabled,
        compute_idle_action_fn=lambda **_kwargs: "turn_off",
        build_idle_action_key_fn=lambda **kwargs: str(kwargs["action"]),
        should_log_idle_action_fn=lambda **_kwargs: False,
        apply_idle_action_fn=lambda _tray, *, action, dim_temp_brightness: applied.append(
            (action, dim_temp_brightness)
        ),
        read_on_ac_power_fn=lambda: False,
    )

    assert applied == [(None, 5)]
    assert loop_state.last_on_ac_power is False
    assert loop_state.last_power_source_change_at == pytest.approx(100.0)
    assert loop_state.backlight_state.baselines == {}
    assert loop_state.backlight_state.dimmed == {}
    assert loop_state.dimmed_true_streak == 0
    assert loop_state.screen_off_true_streak == 0


def test_run_idle_power_iteration_passes_session_idle_for_restore_candidate() -> None:
    from src.tray.idle_power_state import set_idle_power_state_field

    captured: dict[str, object] = {}
    tray = _make_tray(reload_fn=lambda: None, log_event_fn=lambda *_args, **_kwargs: None)
    tray.is_off = True
    set_idle_power_state_field(tray, attr_name="_idle_forced_off", state_name="idle_forced_off", value=True)

    def compute_action(**kwargs):
        captured.update(kwargs)

    _runtime.run_idle_power_iteration(
        tray,
        loop_state=_runtime.IdlePollLoopState(),
        idle_timeout_s=60.0,
        session_id="session-1",
        now_monotonic_fn=lambda: 100.0,
        ensure_idle_state_fn=lambda _tray: None,
        read_dimmed_state_fn=lambda _state: False,
        read_screen_off_state_drm_fn=lambda: False,
        debounce_dim_and_screen_off_fn=lambda **kwargs: (
            kwargs["dimmed_raw"],
            kwargs["screen_off_raw"],
            kwargs["dimmed_true_streak"],
            kwargs["dimmed_false_streak"],
            kwargs["screen_off_true_streak"],
        ),
        read_logind_idle_seconds_fn=lambda **_kwargs: 120.0,
        read_desktop_dim_timeout_fn=lambda _on_ac: None,
        create_wayland_idle_tracker_fn=lambda _timeout_ms: None,
        read_wayland_idle_fn=lambda _tracker: None,
        create_input_idle_tracker_fn=lambda: None,
        read_input_idle_seconds_fn=lambda _tracker: None,
        effective_screen_dim_sync_enabled_fn=lambda _tray, requested_enabled: requested_enabled,
        compute_idle_action_fn=compute_action,
        build_idle_action_key_fn=lambda **kwargs: str(kwargs["action"]),
        should_log_idle_action_fn=lambda **_kwargs: False,
        apply_idle_action_fn=lambda *_args, **_kwargs: None,
    )

    assert captured["dimmed"] is False
    assert captured["session_idle"] is True


def test_run_idle_power_iteration_propagates_unexpected_config_reload_failure() -> None:
    def fail_reload() -> None:
        raise AssertionError("unexpected reload bug")

    tray = _make_tray(reload_fn=fail_reload, log_event_fn=lambda *_args, **_kwargs: None)

    with pytest.raises(AssertionError, match="unexpected reload bug"):
        _runtime.run_idle_power_iteration(
            tray,
            loop_state=_runtime.IdlePollLoopState(),
            idle_timeout_s=60.0,
            session_id=None,
            now_monotonic_fn=lambda: 1.0,
            ensure_idle_state_fn=lambda _tray: None,
            read_dimmed_state_fn=lambda _tray: False,
            read_screen_off_state_drm_fn=lambda: False,
            debounce_dim_and_screen_off_fn=lambda **kwargs: (
                kwargs["dimmed_raw"],
                kwargs["screen_off_raw"],
                kwargs["dimmed_true_streak"],
                kwargs["dimmed_false_streak"],
                kwargs["screen_off_true_streak"],
            ),
            read_logind_idle_seconds_fn=lambda **_kwargs: None,
            read_desktop_dim_timeout_fn=lambda _on_ac: None,
            create_wayland_idle_tracker_fn=lambda _timeout_ms: None,
            read_wayland_idle_fn=lambda _tracker: None,
            create_input_idle_tracker_fn=lambda: None,
            read_input_idle_seconds_fn=lambda _tracker: None,
            effective_screen_dim_sync_enabled_fn=lambda _tray, requested_enabled: requested_enabled,
            compute_idle_action_fn=lambda **_kwargs: "turn_off",
            build_idle_action_key_fn=lambda **_kwargs: "turn_off",
            should_log_idle_action_fn=lambda **_kwargs: False,
            apply_idle_action_fn=lambda *_args, **_kwargs: None,
        )


def test_run_idle_power_iteration_uses_desktop_timeout_and_input_idle_as_primary() -> None:
    captured: dict[str, object] = {}
    tray = _make_tray(reload_fn=lambda: None, log_event_fn=lambda *_args, **_kwargs: None)

    def compute_action(**kwargs):
        captured.update(kwargs)

    _runtime.run_idle_power_iteration(
        tray,
        loop_state=_runtime.IdlePollLoopState(),
        idle_timeout_s=60.0,
        session_id=None,
        now_monotonic_fn=lambda: 100.0,
        ensure_idle_state_fn=lambda _tray: None,
        read_dimmed_state_fn=lambda _state: False,
        read_screen_off_state_drm_fn=lambda: False,
        debounce_dim_and_screen_off_fn=lambda **kwargs: (
            kwargs["dimmed_raw"],
            kwargs["screen_off_raw"],
            kwargs["dimmed_true_streak"],
            kwargs["dimmed_false_streak"],
            kwargs["screen_off_true_streak"],
        ),
        read_logind_idle_seconds_fn=lambda **_kwargs: None,
        read_desktop_dim_timeout_fn=lambda _on_ac: 10.0,
        create_wayland_idle_tracker_fn=lambda _timeout_ms: None,
        read_wayland_idle_fn=lambda _tracker: None,
        create_input_idle_tracker_fn=lambda: object(),
        read_input_idle_seconds_fn=lambda _tracker: 15.0,
        effective_screen_dim_sync_enabled_fn=lambda _tray, requested_enabled: requested_enabled,
        compute_idle_action_fn=compute_action,
        build_idle_action_key_fn=lambda **kwargs: str(kwargs["action"]),
        should_log_idle_action_fn=lambda **_kwargs: False,
        apply_idle_action_fn=lambda *_args, **_kwargs: None,
    )

    assert captured["dimmed"] is True
    assert captured["session_idle"] is True


def test_run_idle_power_iteration_falls_back_to_brightness_when_desktop_timeout_missing() -> None:
    captured: dict[str, object] = {}
    tray = _make_tray(reload_fn=lambda: None, log_event_fn=lambda *_args, **_kwargs: None)

    def compute_action(**kwargs):
        captured.update(kwargs)

    _runtime.run_idle_power_iteration(
        tray,
        loop_state=_runtime.IdlePollLoopState(),
        idle_timeout_s=60.0,
        session_id=None,
        now_monotonic_fn=lambda: 100.0,
        ensure_idle_state_fn=lambda _tray: None,
        read_dimmed_state_fn=lambda _state: True,
        read_screen_off_state_drm_fn=lambda: False,
        debounce_dim_and_screen_off_fn=lambda **kwargs: (
            kwargs["dimmed_raw"],
            kwargs["screen_off_raw"],
            kwargs["dimmed_true_streak"],
            kwargs["dimmed_false_streak"],
            kwargs["screen_off_true_streak"],
        ),
        read_logind_idle_seconds_fn=lambda **_kwargs: None,
        read_desktop_dim_timeout_fn=lambda _on_ac: None,
        create_wayland_idle_tracker_fn=lambda _timeout_ms: None,
        read_wayland_idle_fn=lambda _tracker: None,
        create_input_idle_tracker_fn=lambda: None,
        read_input_idle_seconds_fn=lambda _tracker: None,
        effective_screen_dim_sync_enabled_fn=lambda _tray, requested_enabled: requested_enabled,
        compute_idle_action_fn=compute_action,
        build_idle_action_key_fn=lambda **kwargs: str(kwargs["action"]),
        should_log_idle_action_fn=lambda **_kwargs: False,
        apply_idle_action_fn=lambda *_args, **_kwargs: None,
    )

    assert captured["dimmed"] is True


def test_run_idle_power_iteration_falls_back_to_brightness_when_input_idle_missing() -> None:
    captured: dict[str, object] = {}
    tray = _make_tray(reload_fn=lambda: None, log_event_fn=lambda *_args, **_kwargs: None)

    def compute_action(**kwargs):
        captured.update(kwargs)

    _runtime.run_idle_power_iteration(
        tray,
        loop_state=_runtime.IdlePollLoopState(),
        idle_timeout_s=60.0,
        session_id=None,
        now_monotonic_fn=lambda: 100.0,
        ensure_idle_state_fn=lambda _tray: None,
        read_dimmed_state_fn=lambda _state: True,
        read_screen_off_state_drm_fn=lambda: False,
        debounce_dim_and_screen_off_fn=lambda **kwargs: (
            kwargs["dimmed_raw"],
            kwargs["screen_off_raw"],
            kwargs["dimmed_true_streak"],
            kwargs["dimmed_false_streak"],
            kwargs["screen_off_true_streak"],
        ),
        read_logind_idle_seconds_fn=lambda **_kwargs: None,
        read_desktop_dim_timeout_fn=lambda _on_ac: 10.0,
        create_wayland_idle_tracker_fn=lambda _timeout_ms: None,
        read_wayland_idle_fn=lambda _tracker: None,
        create_input_idle_tracker_fn=lambda: object(),
        read_input_idle_seconds_fn=lambda _tracker: None,
        effective_screen_dim_sync_enabled_fn=lambda _tray, requested_enabled: requested_enabled,
        compute_idle_action_fn=compute_action,
        build_idle_action_key_fn=lambda **kwargs: str(kwargs["action"]),
        should_log_idle_action_fn=lambda **_kwargs: False,
        apply_idle_action_fn=lambda *_args, **_kwargs: None,
    )

    assert captured["dimmed"] is True


def _make_controller_sleep_tray(*, sleep_at: float = 100.0):
    from tests.tray.fakes import make_owner_backed_simple_tray

    tray = make_owner_backed_simple_tray(
        config=SimpleNamespace(brightness=25),
        engine=SimpleNamespace(turn_off=lambda: None),
        is_off=True,
        controller_sleep_off=True,
        controller_sleep_off_at=sleep_at,
        _controller_sleep_off=True,
        _controller_sleep_off_at=sleep_at,
    )
    return tray


def test_controller_sleep_restore_on_new_evdev_input_edge(monkeypatch) -> None:
    tray = _make_controller_sleep_tray(sleep_at=100.0)
    loop_state = _runtime.IdlePollLoopState()
    loop_state.input_idle_tracker = SimpleNamespace(last_keyboard_activity_at=105.0)
    calls: list[object] = []
    tray.engine.turn_off = lambda: calls.append("turn_off")
    monkeypatch.setattr(_runtime, "restore_from_idle", lambda t: calls.append(t))

    _runtime._maybe_restore_from_controller_sleep(tray, loop_state=loop_state, session_idle=None)

    assert calls == ["turn_off", tray]


def test_controller_sleep_restore_stays_armed_when_hardware_rearm_fails(monkeypatch) -> None:
    tray = _make_controller_sleep_tray(sleep_at=100.0)
    loop_state = _runtime.IdlePollLoopState()
    loop_state.input_idle_tracker = SimpleNamespace(last_keyboard_activity_at=105.0)
    calls: list[object] = []

    def fail_turn_off() -> None:
        raise OSError("device unavailable")

    tray.engine.turn_off = fail_turn_off
    monkeypatch.setattr(_runtime, "restore_from_idle", lambda t: calls.append(t))

    _runtime._maybe_restore_from_controller_sleep(tray, loop_state=loop_state, session_idle=None)

    assert calls == []
    assert tray._controller_sleep_off is True


def test_controller_sleep_restore_skipped_while_session_still_idle(monkeypatch) -> None:
    tray = _make_controller_sleep_tray(sleep_at=100.0)
    loop_state = _runtime.IdlePollLoopState()
    loop_state.input_idle_tracker = SimpleNamespace(last_keyboard_activity_at=95.0)
    calls: list[object] = []
    monkeypatch.setattr(_runtime, "restore_from_idle", lambda t: calls.append(t))

    _maybe = _runtime._maybe_restore_from_controller_sleep
    _maybe(tray, loop_state=loop_state, session_idle=True)

    assert calls == []


def test_controller_sleep_restore_skipped_on_known_active_without_input_edge(monkeypatch) -> None:
    """Bare session-active must not soft-on restore (avoids random off→on blinks).

    Level-triggering on session_idle=False combined with transient zero
    misclassified as controller sleep stopped the engine and immediately
    restored — a visible blink while the user was already active.
    """

    tray = _make_controller_sleep_tray(sleep_at=100.0)
    loop_state = _runtime.IdlePollLoopState()
    loop_state.input_idle_tracker = SimpleNamespace(last_keyboard_activity_at=95.0)
    loop_state.prev_session_idle = False
    calls: list[object] = []
    monkeypatch.setattr(_runtime, "restore_from_idle", lambda t: calls.append(t))

    _runtime._maybe_restore_from_controller_sleep(tray, loop_state=loop_state, session_idle=False)

    assert calls == []


def test_controller_sleep_restore_skipped_on_wayland_resume_edge(monkeypatch) -> None:
    tray = _make_controller_sleep_tray(sleep_at=100.0)
    loop_state = _runtime.IdlePollLoopState()
    loop_state.prev_session_idle = True
    loop_state.input_idle_tracker = SimpleNamespace(last_keyboard_activity_at=95.0)
    calls: list[object] = []
    monkeypatch.setattr(_runtime, "restore_from_idle", lambda t: calls.append(t))

    _runtime._maybe_restore_from_controller_sleep(tray, loop_state=loop_state, session_idle=False)

    assert calls == []


def test_controller_sleep_polls_keyboard_tracker_alongside_wayland(monkeypatch) -> None:
    tray = _make_controller_sleep_tray(sleep_at=100.0)
    loop_state = _runtime.IdlePollLoopState(prev_session_idle=True)
    tracker = SimpleNamespace(last_keyboard_activity_at=0.0)
    calls: list[object] = []
    monkeypatch.setattr(_runtime, "restore_from_idle", lambda t: calls.append(t))

    def read_input(_tracker) -> float:
        _tracker.last_keyboard_activity_at = 105.0
        return 0.0

    _runtime._maybe_restore_from_controller_sleep(
        tray,
        loop_state=loop_state,
        session_idle=False,
        create_input_idle_tracker_fn=lambda: tracker,
        read_input_idle_seconds_fn=read_input,
    )

    assert loop_state.input_idle_tracker is tracker
    assert calls == [tray]


def test_controller_sleep_evdev_restore_yields_to_firmware_wake_claim(monkeypatch) -> None:
    """Do not rearm if hardware polling already restored the firmware wake."""

    from src.tray.idle_power_state import set_idle_power_state_field

    tray = _make_controller_sleep_tray(sleep_at=100.0)
    loop_state = _runtime.IdlePollLoopState()
    tracker = SimpleNamespace(last_keyboard_activity_at=0.0)
    calls: list[object] = []
    tray.engine.turn_off = lambda: calls.append("turn_off")
    monkeypatch.setattr(_runtime, "restore_from_idle", lambda t: calls.append(t))

    def read_input(_tracker) -> float:
        _tracker.last_keyboard_activity_at = 105.0
        set_idle_power_state_field(
            tray,
            attr_name="_controller_sleep_off",
            state_name="controller_sleep_off",
            value=False,
        )
        return 0.0

    _runtime._maybe_restore_from_controller_sleep(
        tray,
        loop_state=loop_state,
        session_idle=False,
        create_input_idle_tracker_fn=lambda: tracker,
        read_input_idle_seconds_fn=read_input,
    )

    assert calls == []


def test_screen_idle_off_ignores_wayland_resume_until_keyboard_activity() -> None:
    from src.tray.idle_power_state import set_idle_power_state_field
    from src.tray.pollers.idle_power.policy import compute_idle_action

    tray = _make_tray(reload_fn=lambda: None, log_event_fn=lambda *_args, **_kwargs: None)
    tray.config.controller_sleep_respect = True
    tray.is_off = True
    set_idle_power_state_field(tray, attr_name="_idle_forced_off", state_name="idle_forced_off", value=True)
    set_idle_power_state_field(
        tray,
        attr_name="_last_idle_turn_off_at",
        state_name="last_idle_turn_off_at",
        value=100.0,
    )
    tracker = SimpleNamespace(last_keyboard_activity_at=95.0)
    actions: list[str | None] = []

    _runtime.run_idle_power_iteration(
        tray,
        loop_state=_runtime.IdlePollLoopState(),
        idle_timeout_s=60.0,
        session_id=None,
        now_monotonic_fn=lambda: 240.0,
        ensure_idle_state_fn=lambda _tray: None,
        read_dimmed_state_fn=lambda _state: False,
        read_screen_off_state_drm_fn=lambda: False,
        debounce_dim_and_screen_off_fn=lambda **kwargs: (
            kwargs["dimmed_raw"],
            kwargs["screen_off_raw"],
            kwargs["dimmed_true_streak"],
            kwargs["dimmed_false_streak"],
            kwargs["screen_off_true_streak"],
        ),
        read_logind_idle_seconds_fn=lambda **_kwargs: None,
        read_desktop_dim_timeout_fn=lambda _on_ac: 60.0,
        create_wayland_idle_tracker_fn=lambda _timeout_ms: object(),
        read_wayland_idle_fn=lambda _tracker: False,
        create_input_idle_tracker_fn=lambda: tracker,
        read_input_idle_seconds_fn=lambda _tracker: 0.0,
        effective_screen_dim_sync_enabled_fn=lambda _tray, requested_enabled: requested_enabled,
        compute_idle_action_fn=compute_idle_action,
        build_idle_action_key_fn=lambda **kwargs: str(kwargs["action"]),
        should_log_idle_action_fn=lambda **_kwargs: False,
        apply_idle_action_fn=lambda _tray, *, action, dim_temp_brightness: actions.append(action),
    )

    assert actions == [None]


def test_controller_sleep_restore_noop_without_flag(monkeypatch) -> None:
    from tests.tray.fakes import make_owner_backed_simple_tray

    tray = make_owner_backed_simple_tray(config=SimpleNamespace(brightness=25), engine=SimpleNamespace(), is_off=False)
    loop_state = _runtime.IdlePollLoopState()
    loop_state.input_idle_tracker = SimpleNamespace(last_keyboard_activity_at=999.0)
    calls: list[object] = []
    monkeypatch.setattr(_runtime, "restore_from_idle", lambda t: calls.append(t))

    _runtime._maybe_restore_from_controller_sleep(tray, loop_state=loop_state, session_idle=False)

    assert calls == []
