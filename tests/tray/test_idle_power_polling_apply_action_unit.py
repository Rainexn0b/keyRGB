from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from contextlib import AbstractContextManager

import pytest

from src.tray.controllers._transition_constants import SOFT_OFF_FADE_DURATION_S, SOFT_ON_FADE_DURATION_S
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



def test_dim_to_temp_logs_effect_name_failure_and_falls_back_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.tray.pollers.idle_power._actions as actions_module

    logs: list[tuple[str, str, BaseException | None]] = []

    def fake_log_throttled(_logger, key, *, interval_s, level, msg, exc=None):
        logs.append((key, msg, exc))
        return True

    class BadEffect:
        def __str__(self) -> str:
            raise RuntimeError('bad effect')

    tray = _mk_tray(effect=BadEffect(), brightness=25)
    monkeypatch.setattr(actions_module, 'log_throttled', fake_log_throttled)

    _apply_idle_action(tray, action='dim_to_temp', dim_temp_brightness=7)

    tray.engine.set_brightness.assert_called_once_with(
        7,
        apply_to_hardware=True,
        fade=True,
        fade_duration_s=0.25,
    )
    assert len(logs) == 1
    assert logs[0][0] == 'idle_power.dim_to_temp.effect_name'
    assert logs[0][1] == 'Idle-power dim-to-temp could not read effect name; falling back to none'
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


def test_restore_does_restore_when_not_forced_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.tray.pollers.idle_power.polling as module

    tray = _mk_tray(effect="wave", brightness=25)

    restore = MagicMock()
    monkeypatch.setattr(module, "_restore_from_idle", restore)

    _apply_idle_action(tray, action="restore", dim_temp_brightness=5)

    restore.assert_called_once_with(tray)


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
    assert getattr(engine, "_reactive_transition_from_brightness", None) == 25
    assert getattr(engine, "_reactive_transition_to_brightness", None) == 3
    assert getattr(engine, "_reactive_transition_duration_s", None) == SOFT_OFF_FADE_DURATION_S

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
    assert getattr(engine, "_reactive_transition_from_brightness", None) == 3
    # restore_target_hw = max(config.brightness=5, perkey=5) = 5
    # reactive_brightness is excluded from the target because _resolve_brightness
    # no longer raises hw above global_hw.  Targeting reactive_brightness=50 would
    # overshoot steady-state hw=5 and produce a visible flash on every undim.
    assert getattr(engine, "_reactive_transition_to_brightness", None) == 5
    assert getattr(engine, "_reactive_transition_duration_s", None) == SOFT_ON_FADE_DURATION_S


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
