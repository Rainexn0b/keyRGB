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
