from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from tests.tray.fakes import make_owner_backed_simple_tray


def _idle_tray(**fields: Any) -> SimpleNamespace:
    """Owner-backed idle-power tray with common restore defaults."""
    defaults: dict[str, Any] = {
        "is_off": True,
        "idle_forced_off": True,
        "last_brightness": 33,
        "config": SimpleNamespace(brightness=0),
        "engine": SimpleNamespace(current_color=(12, 34, 56)),
        "_log_exception": lambda *_a, **_kw: None,
        "_start_current_effect": lambda **_kwargs: None,
        "_refresh_ui": lambda: None,
    }
    defaults.update(fields)
    return make_owner_backed_simple_tray(**defaults)


def test_ensure_idle_state_sets_defaults() -> None:
    from keyrgb.tray.idle_power_state import TrayIdlePowerState
    from keyrgb.tray.pollers.idle_power.polling import _ensure_idle_state

    tray = SimpleNamespace()
    _ensure_idle_state(tray)

    assert tray._idle_forced_off is False
    assert tray._user_forced_off is False
    assert tray._power_forced_off is False
    assert tray._dim_temp_active is False
    assert tray._dim_temp_target_brightness is None
    assert isinstance(tray.tray_idle_power_state, TrayIdlePowerState)


def test_ensure_idle_state_syncs_existing_legacy_values_into_state_owner() -> None:
    from keyrgb.tray.pollers.idle_power.polling import _ensure_idle_state

    tray = SimpleNamespace(
        _idle_forced_off=True,
        _user_forced_off=True,
        _power_forced_off=False,
        _dim_temp_active=True,
        _dim_temp_target_brightness=12,
        _dim_sync_suppressed_logged=True,
        _last_resume_at=7.5,
    )

    _ensure_idle_state(tray)

    state = tray.tray_idle_power_state
    assert state.idle_forced_off is True
    assert state.user_forced_off is True
    assert state.power_forced_off is False
    assert state.dim_temp_active is True
    assert state.dim_temp_target_brightness == 12
    assert state.dim_sync_suppressed_logged is True
    assert state.last_resume_at == pytest.approx(7.5)


def test_backlight_state_baselines_persist_across_ensure_idle_state(tmp_path) -> None:
    """Regression: ensure_idle_state must not reset BacklightState baselines.

    After commit 7eda2a4, read_dimmed_state writes to BacklightState owned by
    IdlePollLoopState, but ensure_idle_state still synced legacy tray attrs
    (_dim_backlight_baselines etc.) into the TrayIdlePowerState owner. Because
    the tray attrs were initialized to empty defaults, the second polling
    iteration would copy empty dicts back into state, clobbering baselines and
    causing dim/undim oscillation (visible as keyboard flickering).
    """
    import keyrgb.tray.pollers.idle_power.polling as ipp
    from keyrgb.tray.pollers.idle_power._runtime import IdlePollLoopState, run_idle_power_iteration
    from keyrgb.tray.pollers.idle_power.sensors import read_dimmed_state

    backlight = tmp_path / "sys" / "class" / "backlight" / "intel_backlight"
    backlight.mkdir(parents=True, exist_ok=True)
    (backlight / "max_brightness").write_text("200\n", encoding="utf-8")
    (backlight / "brightness").write_text("100\n", encoding="utf-8")

    tray = make_owner_backed_simple_tray(
        config=SimpleNamespace(
            reload=lambda: None,
            power_management_enabled=True,
            brightness=25,
            screen_dim_sync_enabled=True,
            screen_dim_sync_mode="off",
            screen_dim_temp_brightness=5,
        ),
        is_off=False,
        idle_forced_off=False,
        user_forced_off=False,
        power_forced_off=False,
        dim_temp_active=False,
        dim_temp_target_brightness=None,
        last_resume_at=0.0,
        _dim_sync_suppressed_logged=False,
        _log_event=lambda *_a, **_kw: None,
        engine=SimpleNamespace(),
    )

    loop_state = IdlePollLoopState()
    base = tmp_path / "sys" / "class" / "backlight"

    # First iteration: establishes baseline.
    run_idle_power_iteration(
        tray,
        loop_state=loop_state,
        idle_timeout_s=60.0,
        session_id=None,
        now_monotonic_fn=lambda: 1.0,
        ensure_idle_state_fn=ipp._ensure_idle_state,
        read_dimmed_state_fn=lambda state: read_dimmed_state(state, backlight_base=base),
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
        compute_idle_action_fn=lambda **_kwargs: None,
        build_idle_action_key_fn=lambda **_kwargs: "none",
        should_log_idle_action_fn=lambda **_kwargs: False,
        apply_idle_action_fn=lambda *_a, **_kw: None,
    )

    baseline_key = str(backlight)
    assert loop_state.backlight_state.baselines.get(baseline_key) == 100

    # Second iteration: without the fix, ensure_idle_state would clobber baselines.
    run_idle_power_iteration(
        tray,
        loop_state=loop_state,
        idle_timeout_s=60.0,
        session_id=None,
        now_monotonic_fn=lambda: 1.5,
        ensure_idle_state_fn=ipp._ensure_idle_state,
        read_dimmed_state_fn=lambda state: read_dimmed_state(state, backlight_base=base),
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
        compute_idle_action_fn=lambda **_kwargs: None,
        build_idle_action_key_fn=lambda **_kwargs: "none",
        should_log_idle_action_fn=lambda **_kwargs: False,
        apply_idle_action_fn=lambda *_a, **_kw: None,
    )

    assert loop_state.backlight_state.baselines.get(baseline_key) == 100


def test_read_logind_idle_seconds_parsing_and_monotonic(monkeypatch) -> None:
    import keyrgb.tray.pollers.idle_power.polling as ipp

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
    import keyrgb.tray.pollers.idle_power.polling as ipp

    calls = {"start": 0, "refresh": 0, "log": 0}

    tray = _idle_tray(
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
    assert tray.tray_idle_power_state.idle_forced_off is False
    assert tray.config.brightness == 33
    assert calls["start"] == 1
    assert calls["log"] == 1
    assert calls["refresh"] == 1


def test_restore_from_idle_records_resume_timestamp(monkeypatch) -> None:
    import keyrgb.tray.pollers.idle_power._actions as actions_module
    import keyrgb.tray.pollers.idle_power.polling as ipp

    monkeypatch.setattr(actions_module.time, "monotonic", lambda: 123.0)

    tray = _idle_tray(last_resume_at=0.0)

    ipp._restore_from_idle(tray)

    assert tray._last_resume_at == pytest.approx(123.0)
    assert tray.tray_idle_power_state.last_resume_at == pytest.approx(123.0)


def test_restore_from_idle_syncs_owner_state_fields(monkeypatch) -> None:
    import keyrgb.tray.pollers.idle_power._actions as actions_module
    import keyrgb.tray.pollers.idle_power.polling as ipp

    monkeypatch.setattr(actions_module.time, "monotonic", lambda: 456.0)

    tray = _idle_tray(last_resume_at=0.0)

    ipp._restore_from_idle(tray)

    assert tray._idle_forced_off is False
    assert tray._last_resume_at == pytest.approx(456.0)
    assert tray.tray_idle_power_state.idle_forced_off is False
    assert tray.tray_idle_power_state.last_resume_at == pytest.approx(456.0)


def test_restore_from_idle_refreshes_icon_without_animation_when_supported() -> None:
    import keyrgb.tray.pollers.idle_power.polling as ipp

    calls: dict[str, object] = {"animate_icon": None}

    def capture_refresh(*, animate_icon=True):
        calls["animate_icon"] = animate_icon

    tray = _idle_tray(
        last_resume_at=0.0,
        config=SimpleNamespace(brightness=33, effect="reactive_ripple"),
        _refresh_ui=capture_refresh,
    )

    ipp._restore_from_idle(tray)

    assert calls["animate_icon"] is False


def test_restore_from_idle_loop_effect_uses_soft_on_start() -> None:
    import keyrgb.tray.pollers.idle_power.polling as ipp
    from keyrgb.tray.controllers._power._transition_constants import SOFT_ON_START_BRIGHTNESS

    received: dict[str, object] = {}

    def capture_start(**kwargs):
        received.update(kwargs)

    tray = _idle_tray(
        last_resume_at=0.0,
        config=SimpleNamespace(brightness=33, effect="reactive_ripple"),
        _start_current_effect=capture_start,
    )

    ipp._restore_from_idle(tray)

    assert received["brightness_override"] == SOFT_ON_START_BRIGHTNESS
    assert received["fade_in"] is True


@pytest.mark.parametrize("effect", ["static", "reactive_ripple"])
def test_controller_sleep_restore_preserves_active_temp_dim_policy(effect: str) -> None:
    """KSW-7: evdev-first wake must not bypass temporary screen dim."""

    import keyrgb.tray.pollers.idle_power.polling as ipp

    received: dict[str, object] = {}

    def capture_start(**kwargs):
        received.update(kwargs)

    tray = _idle_tray(
        last_resume_at=0.0,
        dim_temp_active=True,
        dim_temp_target_brightness=5,
        config=SimpleNamespace(brightness=33, effect=effect),
        _start_current_effect=capture_start,
    )

    ipp._restore_from_idle(tray)

    assert received["brightness_override"] == 5
    assert received["fade_in"] is False
    assert tray.tray_idle_power_state.last_resume_at == 0.0
    assert tray.engine._hw_brightness_cap == 5
    assert tray.engine._dim_temp_active is True


def test_restore_from_idle_reactive_effect_seeds_restore_timers_after_restart(
    monkeypatch,
) -> None:
    import keyrgb.tray.pollers.idle_power.polling as ipp
    from keyrgb.core.effects.reactive import _render_brightness_support as reactive_support
    from keyrgb.tray.controllers._power._transition_constants import DEFAULT_IDLE_FADE_DURATION_S

    monkeypatch.setattr("keyrgb.tray.pollers.idle_power._transition_actions.time.monotonic", lambda: 100.0)

    tray = _idle_tray(
        last_resume_at=0.0,
        config=SimpleNamespace(brightness=33, effect="reactive_ripple"),
        engine=SimpleNamespace(
            current_color=(12, 34, 56),
            _reactive_disable_pulse_hw_lift_until=None,
            _reactive_restore_damp_until=None,
            _reactive_restore_phase=reactive_support.ReactiveRestorePhase.NORMAL,
        ),
    )

    ipp._restore_from_idle(tray)
    state = reactive_support.ensure_reactive_state(tray.engine)

    assert state._reactive_disable_pulse_hw_lift_until == pytest.approx(
        100.0 + max(2.0, float(DEFAULT_IDLE_FADE_DURATION_S) + 0.75)
    )
    assert state._reactive_restore_damp_until == pytest.approx(
        100.0 + max(4.0, float(DEFAULT_IDLE_FADE_DURATION_S) + 2.75)
    )
    assert state._reactive_restore_damp_until > state._reactive_disable_pulse_hw_lift_until
    assert state._reactive_restore_phase is reactive_support.ReactiveRestorePhase.FIRST_PULSE_PENDING


def test_restore_from_idle_non_loop_effect_uses_soft_on_start() -> None:
    import keyrgb.tray.controllers._power._transition_constants as transition_constants
    import keyrgb.tray.pollers.idle_power.polling as ipp

    received: dict[str, object] = {}

    def capture_start(**kwargs):
        received.update(kwargs)

    tray = _idle_tray(
        last_resume_at=0.0,
        config=SimpleNamespace(brightness=33, effect="static"),
        _start_current_effect=capture_start,
    )

    ipp._restore_from_idle(tray)

    assert received["brightness_override"] == transition_constants.SOFT_ON_START_BRIGHTNESS
    assert received["fade_in"] is True


def test_restore_from_idle_logs_tray_logger_failure_with_fallback(monkeypatch) -> None:
    import keyrgb.tray.pollers.idle_power._actions as actions_module
    import keyrgb.tray.pollers.idle_power.polling as ipp

    logs: list[tuple[str, str, BaseException | None]] = []

    def fake_log_throttled(_logger, key, *, interval_s, level, msg, exc=None):
        logs.append((key, msg, exc))
        return True

    tray = _idle_tray(
        _start_current_effect=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("restore failed")),
    )

    def broken_log_exception(*_args, **_kwargs):
        raise RuntimeError("log failed")

    tray._log_exception = broken_log_exception
    monkeypatch.setattr(actions_module, "log_throttled", fake_log_throttled)

    ipp._restore_from_idle(tray)

    assert [entry[0] for entry in logs] == [
        "idle_power.restore_from_idle.logger",
        "idle_power.restore_from_idle",
    ]
    assert isinstance(logs[0][2], RuntimeError)
    assert str(logs[0][2]) == "log failed"
    assert isinstance(logs[1][2], RuntimeError)
    assert str(logs[1][2]) == "restore failed"


def test_restore_from_idle_propagates_unexpected_tray_logger_failure() -> None:
    import keyrgb.tray.pollers.idle_power.polling as ipp

    tray = _idle_tray(
        _start_current_effect=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("restore failed")),
        _log_exception=lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("unexpected logger bug")),
    )

    with pytest.raises(AssertionError, match="unexpected logger bug"):
        ipp._restore_from_idle(tray)


def test_restore_from_idle_propagates_unexpected_restore_errors() -> None:
    import keyrgb.tray.pollers.idle_power.polling as ipp

    tray = _idle_tray(
        _start_current_effect=lambda **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected restore bug")),
    )

    with pytest.raises(AssertionError, match="unexpected restore bug"):
        ipp._restore_from_idle(tray)
