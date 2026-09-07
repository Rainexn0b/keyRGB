"""Unit tests for invalid-high brightness recovery."""

from __future__ import annotations

import threading
from types import SimpleNamespace

from keyrgb.tray.pollers.hardware._recovery import (
    _recover_invalid_high_brightness_best_effort,
)
from tests.tray.fakes import make_owner_backed_simple_tray


def _make_recovery_tray(**extra) -> object:
    """Build an owner-backed tray with recovery-relevant legacy attrs preset."""

    config = extra.pop("config_brightness", 25)
    tray = make_owner_backed_simple_tray(
        last_brightness=extra.pop("last_brightness", 25),
        config=type("C", (), {"brightness": config})(),
        **extra,
    )
    return tray


def test_invalid_high_brightness_recovery_invalidates_running_render_cache() -> None:
    writes: list[int] = []
    events: list[str] = []

    class _TrackingLock:
        def __init__(self) -> None:
            self.entries = 0
            self._lock = threading.Lock()

        def __enter__(self):
            self.entries += 1
            self._lock.acquire()
            return self

        def __exit__(self, *_exc) -> None:
            self._lock.release()

    class _Kb:
        def set_brightness(self, brightness: int) -> None:
            writes.append(int(brightness))

    tracking_lock = _TrackingLock()
    engine = SimpleNamespace(
        running=True,
        kb=_Kb(),
        kb_lock=tracking_lock,
        brightness=10,
        _last_hw_mode_brightness=10,
        _last_rendered_brightness=10,
        _last_reactive_per_key_frame_signature=("sig",),
    )
    tray = _make_recovery_tray(is_off=False, config_brightness=10)
    tray.engine = engine
    tray._refresh_ui = lambda **_kw: None
    tray._log_event = lambda _cat, action, **_kw: events.append(str(action))

    result = _recover_invalid_high_brightness_best_effort(tray, current_brightness=60)

    assert result is True
    assert writes == []
    assert engine._last_hw_mode_brightness == 60
    assert engine._last_rendered_brightness == 50
    assert engine._last_reactive_per_key_frame_signature is None
    assert engine._reactive_state._reactive_controller_brightness_handoff_active is True
    assert tracking_lock.entries == 1
    assert events == ["invalid_high_brightness_recover_render_heal"]


def test_invalid_high_brightness_recovery_does_not_claim_stopped_effect_healed() -> None:
    callbacks: list[str] = []
    tray = _make_recovery_tray(is_off=False, config_brightness=10)
    tray.engine = SimpleNamespace(running=False)
    tray._apply_power_source_perkey_profile_transition = lambda: callbacks.append("apply") or True
    tray._start_current_effect = lambda: callbacks.append("start") or True
    tray._refresh_ui = lambda **_kw: None
    tray._log_event = lambda *_a, **_kw: None

    result = _recover_invalid_high_brightness_best_effort(tray, current_brightness=60)

    assert result is False
    assert callbacks == []


def test_successful_invalid_high_brightness_recovery_is_latched_until_valid_read() -> None:
    tray = _make_recovery_tray(is_off=False, config_brightness=10)
    tray.engine = SimpleNamespace(
        running=True,
        kb_lock=threading.Lock(),
        _last_hw_mode_brightness=10,
        _last_reactive_per_key_frame_signature=("sig",),
    )
    tray._refresh_ui = lambda **_kw: None
    tray._log_event = lambda *_a, **_kw: None

    results = [_recover_invalid_high_brightness_best_effort(tray, current_brightness=60) for _attempt in range(4)]

    assert results == [True, False, False, False]
    assert tray.tray_idle_power_state.invalid_high_brightness_recovery_attempt_count == 1
    assert tray.tray_idle_power_state.last_invalid_high_brightness_recovery_at > 0.0


def test_failed_invalid_high_brightness_recovery_is_bounded(monkeypatch) -> None:
    import keyrgb.tray.pollers.hardware._recovery as recovery

    attempts: list[int] = []
    tray = _make_recovery_tray(is_off=False, config_brightness=10)
    tray.engine = SimpleNamespace(running=True)

    def fail_reassert(*_args, **_kwargs) -> bool:
        attempts.append(1)
        return False

    monkeypatch.setattr(recovery, "_reassert_user_mode_while_running_best_effort", fail_reassert)

    results = [_recover_invalid_high_brightness_best_effort(tray, current_brightness=60) for _attempt in range(4)]

    assert results == [False, False, False, False]
    assert len(attempts) == 3
    assert tray.tray_idle_power_state.invalid_high_brightness_recovery_attempt_count == 3


def test_generation_change_during_failed_publication_does_not_consume_budget(monkeypatch) -> None:
    import keyrgb.tray.pollers.hardware._recovery as recovery

    tray = _make_recovery_tray(is_off=False, config_brightness=10)
    tray.engine = SimpleNamespace(running=True, _thread_generation=4)

    def race_restart(*_args, **_kwargs) -> bool:
        tray.engine._thread_generation = 5
        return False

    monkeypatch.setattr(recovery, "_reassert_user_mode_while_running_best_effort", race_restart)

    result = _recover_invalid_high_brightness_best_effort(tray, current_brightness=60)

    assert result is False
    assert tray.tray_idle_power_state.invalid_high_brightness_recovery_attempt_count == 0


def test_new_generation_does_not_inherit_failed_attempt_budget(monkeypatch) -> None:
    import keyrgb.tray.pollers.hardware._recovery as recovery

    calls: list[int] = []
    tray = _make_recovery_tray(is_off=False, config_brightness=10)
    tray.engine = SimpleNamespace(running=True, _thread_generation=5)
    tray.tray_idle_power_state.invalid_high_brightness_recovery_attempt_count = 3
    tray.tray_idle_power_state.invalid_high_brightness_recovery_generation = 4

    def fail_reassert(*_args, **_kwargs) -> bool:
        calls.append(1)
        return False

    monkeypatch.setattr(recovery, "_reassert_user_mode_while_running_best_effort", fail_reassert)

    result = _recover_invalid_high_brightness_best_effort(tray, current_brightness=60)

    assert result is False
    assert calls == [1]
    assert tray.tray_idle_power_state.invalid_high_brightness_recovery_attempt_count == 1
    assert tray.tray_idle_power_state.invalid_high_brightness_recovery_generation == 5


def test_generation_change_during_latch_publication_withdraws_success(monkeypatch) -> None:
    import keyrgb.tray.pollers.hardware._recovery as recovery

    tray = _make_recovery_tray(is_off=False, config_brightness=10)
    tray.engine = SimpleNamespace(running=True, _thread_generation=4)
    monkeypatch.setattr(recovery, "_reassert_user_mode_while_running_best_effort", lambda *_a, **_kw: True)

    def race_stamp(_tray, *, attr_name: str, state_name: str, value) -> None:
        del attr_name
        setattr(tray.tray_idle_power_state, state_name, value)
        if float(value) > 0.0:
            tray.engine._thread_generation = 5

    monkeypatch.setattr(recovery, "set_idle_power_state_field", race_stamp)

    result = _recover_invalid_high_brightness_best_effort(tray, current_brightness=60)

    assert result is False
    assert tray.tray_idle_power_state.invalid_high_brightness_recovery_attempt_count == 0
    assert tray.tray_idle_power_state.last_invalid_high_brightness_recovery_at == 0.0
    assert tray.tray_idle_power_state.invalid_high_brightness_recovery_generation is None


def test_invalid_high_brightness_recovery_withdraws_cache_on_stop_race() -> None:
    class _RacingEngine:
        def __init__(self) -> None:
            object.__setattr__(self, "running", True)
            object.__setattr__(self, "kb_lock", threading.Lock())
            object.__setattr__(self, "_thread_generation", 4)
            object.__setattr__(self, "_last_hw_mode_brightness", 10)
            object.__setattr__(self, "_last_reactive_per_key_frame_signature", ("sig",))
            object.__setattr__(self, "_race_armed", True)

        def __setattr__(self, name, value) -> None:
            object.__setattr__(self, name, value)
            if name == "_last_reactive_per_key_frame_signature" and value is None and self._race_armed:
                object.__setattr__(self, "running", False)
                object.__setattr__(self, "_thread_generation", self._thread_generation + 1)

    tray = _make_recovery_tray(is_off=False, config_brightness=10)
    tray.engine = _RacingEngine()
    tray._refresh_ui = lambda **_kw: None
    tray._log_event = lambda *_a, **_kw: None

    result = _recover_invalid_high_brightness_best_effort(tray, current_brightness=60)

    assert result is False
    assert tray.engine._last_hw_mode_brightness is None
    assert tray.engine._last_rendered_brightness is None
    assert tray.engine._last_reactive_per_key_frame_signature is None
    assert tray.engine._reactive_state._reactive_controller_brightness_handoff_active is False


def test_invalid_high_brightness_helper_leaves_ui_refresh_to_pipeline() -> None:
    refreshes: list[str] = []
    tray = _make_recovery_tray(is_off=False, config_brightness=10)
    tray.engine = SimpleNamespace(
        running=True,
        kb_lock=threading.Lock(),
        _last_hw_mode_brightness=10,
        _last_reactive_per_key_frame_signature=("sig",),
    )
    tray._refresh_ui = lambda **_kw: refreshes.append("refresh")
    tray._log_event = lambda *_a, **_kw: None

    result = _recover_invalid_high_brightness_best_effort(tray, current_brightness=60)

    assert result is True
    assert refreshes == []
