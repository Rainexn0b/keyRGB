from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from contextlib import AbstractContextManager

import pytest

from src.tray.controllers._power._transition_constants import SOFT_OFF_FADE_DURATION_S, SOFT_ON_FADE_DURATION_S
from src.tray.pollers.idle_power.polling import _apply_idle_action


def _mk_tray(*, effect: str = "rainbow_wave", brightness: int = 25) -> MagicMock:
    tray = MagicMock()
    tray.engine = MagicMock()
    tray.config = SimpleNamespace(effect=effect, brightness=brightness)

    tray.is_off = False
    tray._idle_forced_off = False
    tray._user_forced_off = False
    tray._power_forced_off = False

    tray._dim_temp_active = False
    tray._dim_temp_target_brightness = None

    tray._refresh_ui = MagicMock()
    tray._start_current_effect = MagicMock()

    return tray


def test_turn_off_stops_engine_turns_off_and_sets_idle_forced_flag() -> None:
    tray = _mk_tray(effect="wave", brightness=25)

    _apply_idle_action(tray, action="turn_off", dim_temp_brightness=5)

    tray.engine.stop.assert_called_once()
    tray.engine.turn_off.assert_called_once_with(fade=True, fade_duration_s=SOFT_OFF_FADE_DURATION_S)
    assert tray.is_off is True
    assert tray._idle_forced_off is True
    assert tray._dim_temp_active is False
    assert tray._dim_temp_target_brightness is None
    tray._refresh_ui.assert_called_once()
    assert float(tray._last_idle_turn_off_at) > 0.0


def test_turn_off_skips_soft_fade_for_reactive_per_key_effects() -> None:
    tray = _mk_tray(effect="reactive_ripple", brightness=25)
    tray.engine.kb = SimpleNamespace(set_key_colors=MagicMock())

    _apply_idle_action(tray, action="turn_off", dim_temp_brightness=5)

    tray.engine.stop.assert_called_once()
    tray.engine.turn_off.assert_called_once_with(fade=False, fade_duration_s=SOFT_OFF_FADE_DURATION_S)
    assert tray.is_off is True
    assert tray._idle_forced_off is True


def test_turn_off_records_idle_turn_off_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    tray = _mk_tray(effect="wave", brightness=25)

    monkeypatch.setattr("src.tray.pollers.idle_power._action_execution.time.monotonic", lambda: 123.0)

    _apply_idle_action(tray, action="turn_off", dim_temp_brightness=5)

    assert tray._last_idle_turn_off_at == pytest.approx(123.0)


def test_turn_off_keeps_soft_fade_for_reactive_uniform_backend() -> None:
    tray = _mk_tray(effect="reactive_ripple", brightness=25)
    tray.engine.kb = SimpleNamespace()

    _apply_idle_action(tray, action="turn_off", dim_temp_brightness=5)

    tray.engine.stop.assert_called_once()
    tray.engine.turn_off.assert_called_once_with(fade=True, fade_duration_s=SOFT_OFF_FADE_DURATION_S)
    assert tray.is_off is True
    assert tray._idle_forced_off is True


def test_turn_off_logs_recoverable_stop_failure_and_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.tray.pollers.idle_power._actions as actions_module

    logs: list[tuple[str, str, BaseException | None]] = []

    def fake_log_throttled(_logger, key, *, interval_s, level, msg, exc=None):
        logs.append((key, msg, exc))
        return True

    tray = _mk_tray(effect="wave", brightness=25)
    tray.engine.stop.side_effect = RuntimeError("stop failed")
    monkeypatch.setattr(actions_module, "log_throttled", fake_log_throttled)

    _apply_idle_action(tray, action="turn_off", dim_temp_brightness=5)

    tray.engine.stop.assert_called_once()
    tray.engine.turn_off.assert_called_once_with(fade=True, fade_duration_s=SOFT_OFF_FADE_DURATION_S)
    assert logs == [
        (
            "idle_power.turn_off.stop_engine",
            "Idle-power turn-off failed while stopping engine",
            tray.engine.stop.side_effect,
        )
    ]


def test_turn_off_propagates_unexpected_stop_failure() -> None:
    tray = _mk_tray(effect="wave", brightness=25)
    tray.engine.stop.side_effect = AssertionError("unexpected stop bug")

    with pytest.raises(AssertionError, match="unexpected stop bug"):
        _apply_idle_action(tray, action="turn_off", dim_temp_brightness=5)

    tray.engine.turn_off.assert_not_called()
    tray._refresh_ui.assert_not_called()


def test_dim_to_temp_does_nothing_if_tray_is_off() -> None:
    tray = _mk_tray(effect="wave", brightness=25)
    tray.is_off = True

    _apply_idle_action(tray, action="dim_to_temp", dim_temp_brightness=5)

    tray.engine.set_brightness.assert_not_called()
    assert tray._dim_temp_active is False
    assert tray._dim_temp_target_brightness is None


@pytest.mark.parametrize(
    "effect,expected_apply_to_hardware",
    [
        ("rainbow_wave", False),
        ("perkey", True),
        ("wave", True),
    ],
)
def test_dim_to_temp_uses_hw_write_only_for_non_software_effects(effect: str, expected_apply_to_hardware: bool) -> None:
    tray = _mk_tray(effect=effect, brightness=25)

    _apply_idle_action(tray, action="dim_to_temp", dim_temp_brightness=7)

    assert tray._dim_temp_active is True
    assert tray._dim_temp_target_brightness == 7
    tray.engine.set_brightness.assert_called_once_with(
        7,
        apply_to_hardware=expected_apply_to_hardware,
        fade=True,
        fade_duration_s=0.25,
    )


def test_dim_to_temp_uses_legacy_brightness_signature_without_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.tray.pollers.idle_power._actions as actions_module

    logs: list[tuple[str, str, BaseException | None]] = []

    def fake_log_throttled(_logger, key, *, interval_s, level, msg, exc=None):
        logs.append((key, msg, exc))
        return True

    class LegacyBrightnessEngine:
        def __init__(self) -> None:
            self.calls: list[tuple[int, bool]] = []

        def set_brightness(self, brightness: int, *, apply_to_hardware: bool) -> None:
            self.calls.append((int(brightness), bool(apply_to_hardware)))

    tray = _mk_tray(effect="wave", brightness=25)
    tray.engine = LegacyBrightnessEngine()
    monkeypatch.setattr(actions_module, "log_throttled", fake_log_throttled)

    _apply_idle_action(tray, action="dim_to_temp", dim_temp_brightness=7)

    assert tray.engine.calls == [(7, True)]
    assert logs == []


def test_dim_to_temp_logs_recoverable_brightness_write_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.tray.pollers.idle_power._actions as actions_module

    logs: list[tuple[str, str, BaseException | None]] = []

    def fake_log_throttled(_logger, key, *, interval_s, level, msg, exc=None):
        logs.append((key, msg, exc))
        return True

    tray = _mk_tray(effect="wave", brightness=25)
    tray.engine.set_brightness.side_effect = RuntimeError("brightness failed")
    monkeypatch.setattr(actions_module, "log_throttled", fake_log_throttled)

    _apply_idle_action(tray, action="dim_to_temp", dim_temp_brightness=7)

    tray.engine.set_brightness.assert_called_once_with(
        7,
        apply_to_hardware=True,
        fade=True,
        fade_duration_s=0.25,
    )
    assert tray._dim_temp_active is True
    assert tray._dim_temp_target_brightness == 7
    assert len(logs) == 1
    assert logs[0][0] == "idle_power.set_brightness_best_effort"
    assert logs[0][1] == "Idle-power brightness update failed"
    assert isinstance(logs[0][2], RuntimeError)


def test_dim_to_temp_logs_effect_name_failure_and_falls_back_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.tray.pollers.idle_power._actions as actions_module

    logs: list[tuple[str, str, BaseException | None]] = []

    def fake_log_throttled(_logger, key, *, interval_s, level, msg, exc=None):
        logs.append((key, msg, exc))
        return True

    class BadEffect:
        def __str__(self) -> str:
            raise RuntimeError("bad effect")

    tray = _mk_tray(effect=BadEffect(), brightness=25)
    monkeypatch.setattr(actions_module, "log_throttled", fake_log_throttled)

    _apply_idle_action(tray, action="dim_to_temp", dim_temp_brightness=7)

    tray.engine.set_brightness.assert_called_once_with(
        7,
        apply_to_hardware=True,
        fade=True,
        fade_duration_s=0.25,
    )
    assert len(logs) == 1
    assert logs[0][0] == "idle_power.dim_to_temp.effect_name"
    assert logs[0][1] == "Idle-power dim-to-temp could not read effect name; falling back to none"
    assert isinstance(logs[0][2], RuntimeError)


def test_restore_brightness_clears_dim_temp_and_updates_engine_for_running_sw_effect_without_hw_write() -> None:
    tray = _mk_tray(effect="rainbow_wave", brightness=30)
    tray._dim_temp_active = True
    tray._dim_temp_target_brightness = 5

    _apply_idle_action(tray, action="restore_brightness", dim_temp_brightness=5)

    assert tray._dim_temp_active is False
    assert tray._dim_temp_target_brightness is None
    tray.engine.set_brightness.assert_called_once_with(30, apply_to_hardware=False, fade=True, fade_duration_s=0.25)


def test_dim_to_temp_for_reactive_effect_also_updates_perkey_brightness() -> None:
    tray = _mk_tray(effect="reactive_fade", brightness=25)
    tray.config.perkey_brightness = 50

    _apply_idle_action(tray, action="dim_to_temp", dim_temp_brightness=7)

    assert tray._dim_temp_active is True
    assert tray._dim_temp_target_brightness == 7
    # Reactive dim-sync uses instant (no-fade) updates to avoid blocking the
    # render loop under the RLock.  The stability guard in
    # _resolve_brightness() handles smooth visual transitions.
    tray.engine.set_brightness.assert_called_once_with(7, apply_to_hardware=False, fade=False, fade_duration_s=0.0)
    assert tray.engine.per_key_brightness == 7


def test_restore_brightness_for_reactive_effect_restores_perkey_brightness() -> None:
    tray = _mk_tray(effect="reactive_ripple", brightness=30)
    tray.config.perkey_brightness = 55
    tray._dim_temp_active = True
    tray._dim_temp_target_brightness = 5

    _apply_idle_action(tray, action="restore_brightness", dim_temp_brightness=5)

    assert tray._dim_temp_active is False
    assert tray._dim_temp_target_brightness is None
    # Reactive restore uses instant (no-fade) updates.
    tray.engine.set_brightness.assert_called_once_with(30, apply_to_hardware=False, fade=False, fade_duration_s=0.0)
    assert tray.engine.per_key_brightness == 55


def test_restore_brightness_for_reactive_effect_seeds_longer_visual_damp_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.core.effects.reactive import _render_brightness_support as reactive_support

    tray = _mk_tray(effect="reactive_ripple", brightness=30)
    tray.config.perkey_brightness = 55
    tray._dim_temp_active = True
    tray._dim_temp_target_brightness = 5

    monkeypatch.setattr("src.tray.pollers.idle_power._transition_actions.time.monotonic", lambda: 100.0)

    _apply_idle_action(tray, action="restore_brightness", dim_temp_brightness=5)

    expected_hw_lift_until = 100.0 + max(2.0, float(SOFT_ON_FADE_DURATION_S) + 0.75)
    expected_visual_damp_until = 100.0 + max(4.0, float(SOFT_ON_FADE_DURATION_S) + 2.75)
    state = reactive_support.ensure_reactive_state(tray.engine)

    assert state._reactive_disable_pulse_hw_lift_until == pytest.approx(expected_hw_lift_until)
    assert state._reactive_restore_damp_until == pytest.approx(expected_visual_damp_until)
    assert state._reactive_restore_damp_until > state._reactive_disable_pulse_hw_lift_until
    assert state._reactive_restore_phase is reactive_support.ReactiveRestorePhase.FIRST_PULSE_PENDING


def test_restore_brightness_does_nothing_if_tray_is_off() -> None:
    tray = _mk_tray(effect="wave", brightness=30)
    tray.is_off = True
    tray._dim_temp_active = True
    tray._dim_temp_target_brightness = 5

    _apply_idle_action(tray, action="restore_brightness", dim_temp_brightness=5)

    # Still clears dim-temp bookkeeping, but should not turn lights on.
    assert tray._dim_temp_active is False
    assert tray._dim_temp_target_brightness is None
    tray.engine.set_brightness.assert_not_called()


def test_restore_does_not_restore_when_user_forced_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.tray.pollers.idle_power.polling as module

    tray = _mk_tray(effect="wave", brightness=25)
    tray._user_forced_off = True

    restore = MagicMock()
    monkeypatch.setattr(module, "_restore_from_idle", restore)

    _apply_idle_action(tray, action="restore", dim_temp_brightness=5)

    restore.assert_not_called()


def test_restore_does_not_restore_when_owner_user_forced_off_and_legacy_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.tray.pollers.idle_power.polling as module
    from src.tray.protocols import TrayIdlePowerState

    tray = SimpleNamespace(
        engine=MagicMock(),
        config=SimpleNamespace(effect="wave", brightness=25),
        is_off=False,
        _dim_temp_active=True,
        _dim_temp_target_brightness=5,
        tray_idle_power_state=TrayIdlePowerState(
            user_forced_off=True,
            power_forced_off=False,
            dim_temp_active=True,
            dim_temp_target_brightness=5,
        ),
        _refresh_ui=MagicMock(),
        _start_current_effect=MagicMock(),
    )

    restore = MagicMock()
    monkeypatch.setattr(module, "_restore_from_idle", restore)

    _apply_idle_action(tray, action="restore", dim_temp_brightness=5)

    restore.assert_not_called()
    assert tray._user_forced_off is True
    assert tray._power_forced_off is False


def test_restore_does_restore_when_not_forced_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.tray.pollers.idle_power.polling as module

    tray = _mk_tray(effect="wave", brightness=25)

    restore = MagicMock()
    monkeypatch.setattr(module, "_restore_from_idle", restore)

    _apply_idle_action(tray, action="restore", dim_temp_brightness=5)

    restore.assert_called_once_with(tray)


def test_dim_to_temp_skips_when_owner_state_matches_and_legacy_values_are_invalid() -> None:
    from src.tray.protocols import TrayIdlePowerState

    tray = SimpleNamespace(
        engine=MagicMock(),
        config=SimpleNamespace(effect="wave", brightness=25),
        is_off=False,
        _idle_forced_off=False,
        _user_forced_off=False,
        _power_forced_off=False,
        _dim_temp_active=object(),
        _dim_temp_target_brightness=object(),
        tray_idle_power_state=TrayIdlePowerState(
            dim_temp_active=True,
            dim_temp_target_brightness=7,
        ),
        _refresh_ui=MagicMock(),
        _start_current_effect=MagicMock(),
    )

    _apply_idle_action(tray, action="dim_to_temp", dim_temp_brightness=7)

    tray.engine.set_brightness.assert_not_called()
    assert tray._dim_temp_active is True
    assert tray._dim_temp_target_brightness == 7


class _CountingLock(AbstractContextManager[None]):
    def __init__(self) -> None:
        self.enter_count = 0
        self.held = False

    def __enter__(self) -> None:
        self.enter_count += 1
        self.held = True
        return None

    def __exit__(self, exc_type, exc, tb) -> None:
        self.held = False
        return None


class _StrictEngine:
    """Engine stub that enforces 'atomic under kb_lock' updates.

    This is intentionally strict: it will fail if dim-sync code starts
    manipulating reactive brightness, introducing custom ramps, or calling
    set_brightness outside the kb_lock for reactive effects.
    """

    def __init__(self) -> None:
        self.kb_lock = _CountingLock()
        self.brightness = 25
        self.per_key_brightness = 25
        self.reactive_brightness = 50
        self.set_brightness_calls: list[tuple[int, bool, bool, float]] = []

    def set_brightness(self, brightness: int, *, apply_to_hardware: bool, fade: bool, fade_duration_s: float) -> None:
        # For reactive dim-sync we require atomic updates under kb_lock.
        assert self.kb_lock.held is True
        self.set_brightness_calls.append((int(brightness), bool(apply_to_hardware), bool(fade), float(fade_duration_s)))
        self.brightness = int(brightness)


def test_dim_sync_reactive_lock_in_no_flashy_side_effects() -> None:
    from src.core.effects.reactive._render_brightness_support import ensure_reactive_state

    engine = _StrictEngine()
    tray = SimpleNamespace()
    tray.engine = engine
    tray.is_off = False
    tray._idle_forced_off = False
    tray._user_forced_off = False
    tray._power_forced_off = False
    tray._dim_temp_active = False
    tray._dim_temp_target_brightness = None
    tray.config = SimpleNamespace(effect="reactive_ripple", brightness=5, perkey_brightness=5)

    # Dim to temp must be atomic + instant (no sleeping fade under lock), and
    # must not tamper with reactive_brightness.
    _apply_idle_action(tray, action="dim_to_temp", dim_temp_brightness=3)
    assert tray._dim_temp_active is True
    assert tray._dim_temp_target_brightness == 3
    assert engine.kb_lock.enter_count == 1
    assert engine.per_key_brightness == 3
    assert engine.reactive_brightness == 50
    # Reactive dim no longer sets _hw_brightness_cap — the transition +
    # dim_temp_active is sufficient.  The cap would override the transition
    # animation and cause a single-frame flash-to-dark.
    assert not hasattr(engine, "_hw_brightness_cap") or getattr(engine, "_hw_brightness_cap", None) is None
    # _dim_temp_active is propagated directly to the engine so
    # _resolve_brightness() can see it.
    assert getattr(engine, "_dim_temp_active", None) is True
    assert engine.set_brightness_calls == [(3, False, False, 0.0)]
    state = ensure_reactive_state(engine)
    assert state._reactive_transition_from_brightness == 25
    assert state._reactive_transition_to_brightness == 3
    assert state._reactive_transition_duration_s == SOFT_OFF_FADE_DURATION_S

    # Restore must also be atomic + instant, keep reactive_brightness intact.
    tray._dim_temp_active = True
    tray._dim_temp_target_brightness = 3
    _apply_idle_action(tray, action="restore_brightness", dim_temp_brightness=3)
    assert tray._dim_temp_active is False
    assert tray._dim_temp_target_brightness is None
    assert engine.kb_lock.enter_count == 2
    assert engine.per_key_brightness == 5
    assert engine.reactive_brightness == 50
    # Cap cleared and _dim_temp_active reset on engine.
    assert getattr(engine, "_hw_brightness_cap", "MISSING") is None
    assert getattr(engine, "_dim_temp_active", None) is False
    assert engine.set_brightness_calls[-1] == (5, False, False, 0.0)
    state = ensure_reactive_state(engine)
    assert state._reactive_transition_from_brightness == 3
    # restore_target_hw = max(config.brightness=5, perkey=5) = 5
    # reactive_brightness is excluded from the target because _resolve_brightness
    # no longer raises hw above global_hw.  Targeting reactive_brightness=50 would
    # overshoot steady-state hw=5 and produce a visible flash on every undim.
    assert state._reactive_transition_to_brightness == 5
    assert state._reactive_transition_duration_s == SOFT_ON_FADE_DURATION_S


class _SequencingLock(AbstractContextManager[None]):
    def __init__(self, events: list[str]) -> None:
        self._events = events
        self.held = False

    def __enter__(self) -> None:
        self.held = True
        self._events.append("lock_enter")
        return None

    def __exit__(self, exc_type, exc, tb) -> None:
        self._events.append("lock_exit")
        self.held = False
        return None


class _OrderingEngine:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.kb_lock = _SequencingLock(self.events)
        self.brightness = 25
        self._per_key_brightness = 25

    @property
    def per_key_brightness(self) -> int:
        return int(self._per_key_brightness)

    @per_key_brightness.setter
    def per_key_brightness(self, value: int) -> None:
        assert self.kb_lock.held is True
        self.events.append("set_per_key_brightness")
        self._per_key_brightness = int(value)

    def set_brightness(self, brightness: int, *, apply_to_hardware: bool, fade: bool, fade_duration_s: float) -> None:
        assert self.kb_lock.held is True
        self.events.append("set_brightness")
        self.brightness = int(brightness)
        assert apply_to_hardware is False
        # Reactive dim-sync now uses instant (no-fade) updates.
        assert fade is False
        assert float(fade_duration_s) == 0.0


def test_dim_sync_reactive_ordering_under_lock() -> None:
    engine = _OrderingEngine()
    tray = SimpleNamespace()
    tray.engine = engine
    tray.is_off = False
    tray._idle_forced_off = False
    tray._user_forced_off = False
    tray._power_forced_off = False
    tray._dim_temp_active = False
    tray._dim_temp_target_brightness = None
    tray.config = SimpleNamespace(effect="reactive_ripple", brightness=5, perkey_brightness=5)

    _apply_idle_action(tray, action="dim_to_temp", dim_temp_brightness=3)
    assert engine.events == ["lock_enter", "set_per_key_brightness", "set_brightness", "lock_exit"]

    engine.events.clear()
    tray._dim_temp_active = True
    tray._dim_temp_target_brightness = 3
    _apply_idle_action(tray, action="restore_brightness", dim_temp_brightness=3)
    assert engine.events == ["lock_enter", "set_per_key_brightness", "set_brightness", "lock_exit"]
