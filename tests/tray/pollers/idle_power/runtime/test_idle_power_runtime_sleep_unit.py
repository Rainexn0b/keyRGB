from __future__ import annotations

from types import SimpleNamespace

from keyrgb.tray.pollers.idle_power import _runtime


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


def _make_controller_sleep_tray(*, sleep_at: float = 100.0):
    from tests.tray.fakes import make_owner_backed_simple_tray

    tray = make_owner_backed_simple_tray(
        config=SimpleNamespace(brightness=25),
        engine=SimpleNamespace(
            turn_off=lambda: None,
            kb=SimpleNamespace(keyrgb_controller_wake_settle_s=0.0),
        ),
        _start_current_effect=lambda **_kwargs: True,
        _refresh_ui=lambda **_kwargs: None,
        is_off=True,
        controller_sleep_off=True,
        controller_sleep_off_at=sleep_at,
        _controller_sleep_off=True,
        _controller_sleep_off_at=sleep_at,
    )
    return tray


def test_controller_sleep_restore_on_new_evdev_input_edge() -> None:
    from keyrgb.tray.idle_power_state import set_idle_power_state_field

    tray = _make_controller_sleep_tray(sleep_at=100.0)
    loop_state = _runtime.IdlePollLoopState()
    loop_state.input_idle_tracker = SimpleNamespace(last_keyboard_activity_at=105.0)
    calls: list[object] = []
    refreshed: list[tuple[bool, bool]] = []
    set_idle_power_state_field(tray, attr_name="_idle_forced_off", state_name="idle_forced_off", value=True)
    tray.engine.turn_off = lambda: (_ for _ in ()).throw(AssertionError("must not force off native wake"))
    tray._start_current_effect = lambda **kwargs: calls.append(kwargs) or True
    tray._refresh_ui = lambda **_kwargs: refreshed.append(
        (bool(tray.is_off), bool(tray.tray_idle_power_state.idle_forced_off))
    )

    _runtime._maybe_restore_from_controller_sleep(tray, loop_state=loop_state, session_idle=None)

    assert calls == [{"controller_brightness_handoff": 50}]
    assert refreshed == [(False, False)]


def test_controller_sleep_restore_stays_armed_when_native_handoff_fails() -> None:
    tray = _make_controller_sleep_tray(sleep_at=100.0)
    loop_state = _runtime.IdlePollLoopState()
    loop_state.input_idle_tracker = SimpleNamespace(last_keyboard_activity_at=105.0)
    calls: list[object] = []

    tray.engine.turn_off = lambda: (_ for _ in ()).throw(AssertionError("must not force off native wake"))
    tray._start_current_effect = lambda **kwargs: calls.append(kwargs) or False

    _runtime._maybe_restore_from_controller_sleep(tray, loop_state=loop_state, session_idle=None)

    assert calls == [{"controller_brightness_handoff": 50}]
    assert tray._controller_sleep_off is True


def test_controller_sleep_restore_skipped_while_session_still_idle() -> None:
    tray = _make_controller_sleep_tray(sleep_at=100.0)
    loop_state = _runtime.IdlePollLoopState()
    loop_state.input_idle_tracker = SimpleNamespace(last_keyboard_activity_at=95.0)
    calls: list[object] = []
    tray._start_current_effect = lambda **kwargs: calls.append(kwargs) or True

    _maybe = _runtime._maybe_restore_from_controller_sleep
    _maybe(tray, loop_state=loop_state, session_idle=True)

    assert calls == []


def test_controller_sleep_restore_skipped_on_known_active_without_input_edge() -> None:
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
    tray._start_current_effect = lambda **kwargs: calls.append(kwargs) or True

    _runtime._maybe_restore_from_controller_sleep(tray, loop_state=loop_state, session_idle=False)

    assert calls == []


def test_controller_sleep_restore_skipped_on_wayland_resume_edge() -> None:
    tray = _make_controller_sleep_tray(sleep_at=100.0)
    loop_state = _runtime.IdlePollLoopState()
    loop_state.prev_session_idle = True
    loop_state.input_idle_tracker = SimpleNamespace(last_keyboard_activity_at=95.0)
    calls: list[object] = []
    tray._start_current_effect = lambda **kwargs: calls.append(kwargs) or True

    _runtime._maybe_restore_from_controller_sleep(tray, loop_state=loop_state, session_idle=False)

    assert calls == []


def test_controller_sleep_polls_keyboard_tracker_alongside_wayland() -> None:
    tray = _make_controller_sleep_tray(sleep_at=100.0)
    loop_state = _runtime.IdlePollLoopState(prev_session_idle=True)
    tracker = SimpleNamespace(last_keyboard_activity_at=0.0)
    calls: list[object] = []
    tray._start_current_effect = lambda **kwargs: calls.append(kwargs) or True

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
    assert calls == [{"controller_brightness_handoff": 50}]


def test_controller_sleep_evdev_restore_yields_to_firmware_wake_claim() -> None:
    """Do not rearm if hardware polling already restored the firmware wake."""

    from keyrgb.tray.idle_power_state import set_idle_power_state_field

    tray = _make_controller_sleep_tray(sleep_at=100.0)
    loop_state = _runtime.IdlePollLoopState()
    tracker = SimpleNamespace(last_keyboard_activity_at=0.0)
    calls: list[object] = []
    tray._start_current_effect = lambda **kwargs: calls.append(kwargs) or True

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
    from keyrgb.tray.idle_power_state import set_idle_power_state_field
    from keyrgb.tray.pollers.idle_power.policy import compute_idle_action

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


def test_controller_sleep_restore_event_waits_for_actual_relight(caplog) -> None:
    """With a backend wake-settle delay, the first evdev arm must not journal
    a restore: the deck is still dark, the arm event is authoritative, and a
    duplicate stays quiet. Delay-zero backends still log the immediate restore.
    """

    import logging

    with caplog.at_level(logging.INFO, logger="keyrgb.tray.pollers.idle_power._runtime"):
        tray = _make_controller_sleep_tray(sleep_at=100.0)
        tray.engine.kb = SimpleNamespace(keyrgb_controller_wake_settle_s=2.0)
        tray._start_current_effect = lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("settle arm must not restart the effect")
        )
        loop_state = _runtime.IdlePollLoopState()
        loop_state.input_idle_tracker = SimpleNamespace(last_keyboard_activity_at=105.0)

        _runtime._maybe_restore_from_controller_sleep(tray, loop_state=loop_state, session_idle=None)

        assert tray._controller_sleep_off is True
        assert tray.tray_idle_power_state.controller_wake_settle_until > 0
        assert [record for record in caplog.records if "controller_sleep_restore" in record.getMessage()] == []

        caplog.clear()
        loop_state.input_idle_tracker = SimpleNamespace(last_keyboard_activity_at=106.0)
        _runtime._maybe_restore_from_controller_sleep(tray, loop_state=loop_state, session_idle=None)

        assert tray.tray_idle_power_state.controller_wake_settle_until > 0
        assert [record for record in caplog.records if "controller_sleep_restore" in record.getMessage()] == []

    with caplog.at_level(logging.INFO, logger="keyrgb.tray.pollers.idle_power._runtime"):
        immediate = _make_controller_sleep_tray(sleep_at=100.0)
        immediate.engine.turn_off = lambda: (_ for _ in ()).throw(AssertionError("must not force off native wake"))
        start_calls: list[object] = []
        immediate._start_current_effect = lambda **kwargs: start_calls.append(kwargs) or True
        immediate_loop_state = _runtime.IdlePollLoopState()
        immediate_loop_state.input_idle_tracker = SimpleNamespace(last_keyboard_activity_at=105.0)

        _runtime._maybe_restore_from_controller_sleep(immediate, loop_state=immediate_loop_state, session_idle=None)

        assert start_calls == [{"controller_brightness_handoff": 50}]
        assert [record for record in caplog.records if "controller_sleep_restore" in record.getMessage()]


def test_controller_sleep_restore_noop_without_flag(monkeypatch) -> None:
    from tests.tray.fakes import make_owner_backed_simple_tray

    tray = make_owner_backed_simple_tray(config=SimpleNamespace(brightness=25), engine=SimpleNamespace(), is_off=False)
    loop_state = _runtime.IdlePollLoopState()
    loop_state.input_idle_tracker = SimpleNamespace(last_keyboard_activity_at=999.0)
    calls: list[object] = []
    monkeypatch.setattr(_runtime, "restore_from_idle", lambda t: calls.append(t))

    _runtime._maybe_restore_from_controller_sleep(tray, loop_state=loop_state, session_idle=False)

    assert calls == []
