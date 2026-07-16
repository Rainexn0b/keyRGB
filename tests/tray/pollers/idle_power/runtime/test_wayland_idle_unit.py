from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from src.tray.pollers.idle_power import _runtime
from src.tray.pollers.idle_power._wayland_idle import create_wayland_idle_tracker


class _FakeWaylandIdleTracker:
    def __init__(self, *, idle: bool | None = False):
        self.timeout_ms: int | None = None
        self.closed = False
        self._idle = idle

    def set_timeout_ms(self, timeout_ms: int) -> None:
        self.timeout_ms = timeout_ms

    def is_idle(self) -> bool | None:
        return self._idle

    def close(self) -> None:
        self.closed = True


def test_create_wayland_idle_tracker_returns_none_without_wayland_display() -> None:
    assert create_wayland_idle_tracker(timeout_ms=1000, display_name_or_fd="definitely-not-a-real-display") is None


def test_read_wayland_dimmed_state_creates_tracker_and_returns_idle() -> None:
    fake_tracker = _FakeWaylandIdleTracker(idle=True)
    loop_state = _runtime.IdlePollLoopState()

    def create_tracker(timeout_ms: int) -> Any:
        fake_tracker.timeout_ms = timeout_ms
        return fake_tracker

    result = _runtime._read_wayland_dimmed_state(
        loop_state=loop_state,
        timeout_s=7.5,
        create_wayland_idle_tracker_fn=create_tracker,
        read_wayland_idle_fn=lambda tracker: tracker.is_idle(),
    )

    assert result is True
    assert loop_state.wayland_idle_tracker is fake_tracker
    assert fake_tracker.timeout_ms == 7500


def test_read_wayland_dimmed_state_updates_existing_tracker_timeout() -> None:
    fake_tracker = _FakeWaylandIdleTracker(idle=False)
    loop_state = _runtime.IdlePollLoopState()
    loop_state.wayland_idle_tracker = fake_tracker

    result = _runtime._read_wayland_dimmed_state(
        loop_state=loop_state,
        timeout_s=12.0,
        create_wayland_idle_tracker_fn=lambda _timeout_ms: pytest.fail("should reuse existing tracker"),  # type: ignore[return-value]
        read_wayland_idle_fn=lambda tracker: tracker.is_idle(),
    )

    assert result is False
    assert fake_tracker.timeout_ms == 12000


def test_read_desktop_dimmed_state_prefers_wayland_over_input_idle() -> None:
    loop_state = _runtime.IdlePollLoopState()

    dimmed, session_idle = _runtime._read_desktop_dimmed_state(
        loop_state=loop_state,
        on_ac_power=True,
        read_desktop_dim_timeout_fn=lambda _on_ac: 10.0,
        create_wayland_idle_tracker_fn=lambda _timeout_ms: _FakeWaylandIdleTracker(idle=True),
        read_wayland_idle_fn=lambda tracker: tracker.is_idle(),
        create_input_idle_tracker_fn=lambda: pytest.fail("should not create input tracker when Wayland works"),
        read_input_idle_seconds_fn=lambda _tracker: pytest.fail("should not read input idle when Wayland works"),
        fallback_timeout_s=60.0,
    )

    assert dimmed is True
    assert session_idle is True


def test_read_desktop_dimmed_state_falls_back_to_input_idle_when_wayland_returns_none() -> None:
    loop_state = _runtime.IdlePollLoopState()

    dimmed, session_idle = _runtime._read_desktop_dimmed_state(
        loop_state=loop_state,
        on_ac_power=True,
        read_desktop_dim_timeout_fn=lambda _on_ac: 10.0,
        create_wayland_idle_tracker_fn=lambda _timeout_ms: None,
        read_wayland_idle_fn=lambda _tracker: None,
        create_input_idle_tracker_fn=lambda: object(),  # type: ignore[arg-type,return-value]
        read_input_idle_seconds_fn=lambda _tracker: 15.0,
        fallback_timeout_s=60.0,
    )

    assert dimmed is True
    assert session_idle is True


def test_run_idle_power_iteration_uses_wayland_idle_as_primary() -> None:
    from tests.tray.fakes import make_owner_backed_simple_tray

    captured: dict[str, object] = {}
    tray = make_owner_backed_simple_tray(
        config=SimpleNamespace(
            reload=lambda: None,
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
        _log_event=lambda *_args, **_kwargs: None,
    )

    def compute_action(**kwargs):
        captured.update(kwargs)
        return None

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
        create_wayland_idle_tracker_fn=lambda _timeout_ms: _FakeWaylandIdleTracker(idle=True),
        read_wayland_idle_fn=lambda tracker: tracker.is_idle(),
        create_input_idle_tracker_fn=lambda: pytest.fail("input idle fallback should not be used"),  # type: ignore[return-value]
        read_input_idle_seconds_fn=lambda _tracker: pytest.fail("input idle fallback should not be used"),
        effective_screen_dim_sync_enabled_fn=lambda _tray, requested_enabled: requested_enabled,
        compute_idle_action_fn=compute_action,
        build_idle_action_key_fn=lambda **kwargs: str(kwargs["action"]),
        should_log_idle_action_fn=lambda **_kwargs: False,
        apply_idle_action_fn=lambda *_args, **_kwargs: None,
    )

    assert captured["dimmed"] is True
    assert captured["session_idle"] is True


# ---------------------------------------------------------------------------
# Regression tests for the brightness-heuristic reactivation bug.
#
# Root cause: when the KDE dim timeout (DimDisplayIdleTimeoutSec) was not
# configured for the active power profile, _read_desktop_dimmed_state
# returned (None, None) immediately, skipping the Wayland idle tracker
# entirely.  The brightness heuristic then fired on manual screen-brightness
# changes, turning the keyboard off even though the user was actively
# interacting with the system.
# ---------------------------------------------------------------------------


def test_read_desktop_dimmed_state_uses_fallback_timeout_when_kde_dim_timeout_is_none() -> None:
    """When the KDE dim timeout is None, the fallback timeout should still
    drive the Wayland tracker so manual brightness changes don't trigger the
    brightness heuristic."""
    loop_state = _runtime.IdlePollLoopState()
    created_timeout_ms: list[int] = []

    def create_tracker(timeout_ms: int) -> Any:
        created_timeout_ms.append(timeout_ms)
        return _FakeWaylandIdleTracker(idle=False)

    dimmed, session_idle = _runtime._read_desktop_dimmed_state(
        loop_state=loop_state,
        on_ac_power=False,
        read_desktop_dim_timeout_fn=lambda _on_ac: None,  # KDE dim timeout not configured
        create_wayland_idle_tracker_fn=create_tracker,
        read_wayland_idle_fn=lambda tracker: tracker.is_idle(),
        create_input_idle_tracker_fn=lambda: pytest.fail("should not need evdev when Wayland works"),
        read_input_idle_seconds_fn=lambda _tracker: pytest.fail("should not need evdev when Wayland works"),
        fallback_timeout_s=60.0,
    )

    assert dimmed is False
    assert session_idle is False
    # The tracker should have been created with the fallback timeout (60s = 60000ms),
    # not skipped because the KDE dim timeout was None.
    assert created_timeout_ms == [60000]


def test_read_wayland_dimmed_state_drops_broken_tracker_for_recovery() -> None:
    """When is_idle() returns None (broken connection), the cached tracker
    should be closed and dropped so the next poll recreates a fresh tracker."""
    fake_tracker = _FakeWaylandIdleTracker(idle=None)  # None = broken
    loop_state = _runtime.IdlePollLoopState()
    loop_state.wayland_idle_tracker = fake_tracker

    create_count = 0

    def create_tracker(timeout_ms: int) -> Any:
        nonlocal create_count
        create_count += 1
        return _FakeWaylandIdleTracker(idle=False)

    result = _runtime._read_wayland_dimmed_state(
        loop_state=loop_state,
        timeout_s=10.0,
        create_wayland_idle_tracker_fn=create_tracker,
        read_wayland_idle_fn=lambda tracker: tracker.is_idle(),
    )

    # The broken tracker returned None.
    assert result is None
    # The broken tracker should have been closed.
    assert fake_tracker.closed
    # The cached tracker should be dropped so next poll recreates.
    assert loop_state.wayland_idle_tracker is None
    # create_tracker should NOT have been called this poll (recreation happens
    # on the *next* poll, not immediately).
    assert create_count == 0

    # On the next poll, a fresh tracker should be created.
    result2 = _runtime._read_wayland_dimmed_state(
        loop_state=loop_state,
        timeout_s=10.0,
        create_wayland_idle_tracker_fn=create_tracker,
        read_wayland_idle_fn=lambda tracker: tracker.is_idle(),
    )

    assert result2 is False
    assert create_count == 1
    assert loop_state.wayland_idle_tracker is not None


def test_run_idle_power_iteration_uses_wayland_via_fallback_when_kde_dim_timeout_none() -> None:
    """Integration: when KDE dim timeout is None but Wayland is available,
    the iteration should use the Wayland tracker with the general idle
    timeout and NOT fall back to the brightness heuristic."""
    from tests.tray.fakes import make_owner_backed_simple_tray

    captured: dict[str, object] = {}
    tray = make_owner_backed_simple_tray(
        config=SimpleNamespace(
            reload=lambda: None,
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
        _log_event=lambda *_args, **_kwargs: None,
    )

    def compute_action(**kwargs):
        captured.update(kwargs)
        return None

    _runtime.run_idle_power_iteration(
        tray,
        loop_state=_runtime.IdlePollLoopState(),
        idle_timeout_s=60.0,
        session_id=None,
        now_monotonic_fn=lambda: 100.0,
        ensure_idle_state_fn=lambda _tray: None,
        # The brightness heuristic should NOT be consulted.
        read_dimmed_state_fn=lambda _state: pytest.fail("brightness heuristic should not fire when Wayland is available"),
        read_screen_off_state_drm_fn=lambda: False,
        debounce_dim_and_screen_off_fn=lambda **kwargs: (
            kwargs["dimmed_raw"],
            kwargs["screen_off_raw"],
            kwargs["dimmed_true_streak"],
            kwargs["dimmed_false_streak"],
            kwargs["screen_off_true_streak"],
        ),
        read_logind_idle_seconds_fn=lambda **_kwargs: None,
        read_desktop_dim_timeout_fn=lambda _on_ac: None,  # KDE dim timeout not configured
        create_wayland_idle_tracker_fn=lambda _timeout_ms: _FakeWaylandIdleTracker(idle=False),
        read_wayland_idle_fn=lambda tracker: tracker.is_idle(),
        create_input_idle_tracker_fn=lambda: pytest.fail("evdev should not be needed when Wayland works"),
        read_input_idle_seconds_fn=lambda _tracker: pytest.fail("evdev should not be needed when Wayland works"),
        effective_screen_dim_sync_enabled_fn=lambda _tray, requested_enabled: requested_enabled,
        compute_idle_action_fn=compute_action,
        build_idle_action_key_fn=lambda **kwargs: str(kwargs["action"]),
        should_log_idle_action_fn=lambda **_kwargs: False,
        apply_idle_action_fn=lambda *_args, **_kwargs: None,
    )

    # dimmed should come from Wayland (False = not idle), not the heuristic.
    assert captured["dimmed"] is False
    assert captured["session_idle"] is False
