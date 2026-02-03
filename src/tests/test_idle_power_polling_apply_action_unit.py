from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

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
    tray.engine.set_brightness.assert_called_once_with(7, apply_to_hardware=False, fade=False, fade_duration_s=0.0)
    assert tray.engine.per_key_brightness == 7
    assert tray.engine._dim_temp_active is True


def test_restore_brightness_for_reactive_effect_restores_perkey_brightness() -> None:
    tray = _mk_tray(effect="reactive_ripple", brightness=30)
    tray.config.perkey_brightness = 55
    tray._dim_temp_active = True
    tray._dim_temp_target_brightness = 5
    tray.engine._dim_temp_active = True

    _apply_idle_action(tray, action="restore_brightness", dim_temp_brightness=5)

    assert tray._dim_temp_active is False
    assert tray._dim_temp_target_brightness is None
    tray.engine.set_brightness.assert_called_once_with(30, apply_to_hardware=False, fade=False, fade_duration_s=0.0)
    assert tray.engine.per_key_brightness == 55
    assert tray.engine._dim_temp_active is False


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
