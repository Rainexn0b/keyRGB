from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.tray.pollers.idle_power import _runtime


def _make_tray(*, reload_fn, log_event_fn):
    return SimpleNamespace(
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
        _idle_forced_off=False,
        _user_forced_off=False,
        _power_forced_off=False,
        _dim_backlight_baselines={},
        _dim_backlight_dimmed={},
        _dim_temp_active=False,
        _dim_temp_target_brightness=None,
        _dim_screen_off=False,
        _dim_sync_suppressed_logged=False,
        _last_resume_at=0.0,
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
        effective_screen_dim_sync_enabled_fn=lambda _tray, requested_enabled: requested_enabled,
        compute_idle_action_fn=lambda **_kwargs: "turn_off",
        build_idle_action_key_fn=lambda **_kwargs: "turn_off",
        should_log_idle_action_fn=lambda **_kwargs: False,
        apply_idle_action_fn=lambda _tray, *, action, dim_temp_brightness: applied.append(
            (action, dim_temp_brightness)
        ),
    )

    assert applied == [("turn_off", 5)]


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
            effective_screen_dim_sync_enabled_fn=lambda _tray, requested_enabled: requested_enabled,
            compute_idle_action_fn=lambda **_kwargs: "turn_off",
            build_idle_action_key_fn=lambda **_kwargs: "turn_off",
            should_log_idle_action_fn=lambda **_kwargs: False,
            apply_idle_action_fn=lambda *_args, **_kwargs: None,
        )
