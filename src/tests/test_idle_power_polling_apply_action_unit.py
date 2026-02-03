from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from contextlib import AbstractContextManager

import pytest

from src.tray.pollers.idle_power_polling import _apply_idle_action


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
    tray.engine.turn_off.assert_called_once_with(fade=True, fade_duration_s=0.12)
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
    tray.engine.set_brightness.assert_called_once_with(7, apply_to_hardware=False, fade=True, fade_duration_s=0.25)
    assert tray.engine.per_key_brightness == 7


def test_restore_brightness_for_reactive_effect_restores_perkey_brightness() -> None:
    tray = _mk_tray(effect="reactive_ripple", brightness=30)
    tray.config.perkey_brightness = 55
    tray._dim_temp_active = True
    tray._dim_temp_target_brightness = 5

    _apply_idle_action(tray, action="restore_brightness", dim_temp_brightness=5)

    assert tray._dim_temp_active is False
    assert tray._dim_temp_target_brightness is None
    tray.engine.set_brightness.assert_called_once_with(30, apply_to_hardware=False, fade=True, fade_duration_s=0.25)
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
    from src.tray.pollers import idle_power_polling as module

    tray = _mk_tray(effect="wave", brightness=25)
    tray._user_forced_off = True

    restore = MagicMock()
    monkeypatch.setattr(module, "_restore_from_idle", restore)

    _apply_idle_action(tray, action="restore", dim_temp_brightness=5)

    restore.assert_not_called()


def test_restore_does_restore_when_not_forced_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.tray.pollers import idle_power_polling as module

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

    # Dim to temp must be atomic + use fade, and must not tamper with
    # reactive_brightness or introduce ramp attributes.
    _apply_idle_action(tray, action="dim_to_temp", dim_temp_brightness=3)
    assert tray._dim_temp_active is True
    assert tray._dim_temp_target_brightness == 3
    assert engine.kb_lock.enter_count == 1
    assert engine.per_key_brightness == 3
    assert engine.reactive_brightness == 50
    assert engine.set_brightness_calls == [(3, False, True, 0.25)]
    assert not hasattr(engine, "_keyrgb_hw_ramp_start_at")
    assert not hasattr(engine, "_dim_temp_active")

    # Restore must also be atomic + use fade, keep reactive_brightness intact.
    tray._dim_temp_active = True
    tray._dim_temp_target_brightness = 3
    _apply_idle_action(tray, action="restore_brightness", dim_temp_brightness=3)
    assert tray._dim_temp_active is False
    assert tray._dim_temp_target_brightness is None
    assert engine.kb_lock.enter_count == 2
    assert engine.per_key_brightness == 5
    assert engine.reactive_brightness == 50
    assert engine.set_brightness_calls[-1] == (5, False, True, 0.25)
    assert not hasattr(engine, "_keyrgb_hw_ramp_start_at")
    assert not hasattr(engine, "_dim_temp_active")


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
        assert fade is True
        assert abs(float(fade_duration_s) - 0.25) < 1e-9


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
