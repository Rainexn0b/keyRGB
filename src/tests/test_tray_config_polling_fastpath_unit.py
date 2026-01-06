from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.tray.pollers.config_polling import ConfigApplyState, _maybe_apply_fast_path


def _mk_tray(*, engine_running: bool = True) -> MagicMock:
    tray = MagicMock()
    tray.engine = MagicMock()
    tray.engine.running = engine_running
    tray.config = SimpleNamespace(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        per_key_colors={},
        reactive_use_manual_color=False,
        reactive_color=(10, 20, 30),
    )
    return tray


def test_fastpath_reactive_change_updates_engine_without_restart() -> None:
    tray = _mk_tray(engine_running=True)

    last = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )
    current = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=True,
        reactive_color=(10, 20, 30),
    )

    handled, new_last = _maybe_apply_fast_path(tray, last_applied=last, current=current)

    assert handled is True
    assert new_last == current
    assert tray.engine.reactive_use_manual_color is True
    assert tray.engine.reactive_color == (10, 20, 30)
    tray.engine.set_brightness.assert_not_called()


def test_fastpath_brightness_change_for_running_sw_effect_does_not_restart_and_no_hw_write() -> None:
    tray = _mk_tray(engine_running=True)

    last = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )
    current = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=30,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )

    handled, new_last = _maybe_apply_fast_path(tray, last_applied=last, current=current)

    assert handled is True
    assert new_last == current
    tray.engine.set_brightness.assert_called_once_with(30, apply_to_hardware=False)


def test_fastpath_brightness_change_not_taken_if_engine_not_running() -> None:
    tray = _mk_tray(engine_running=False)

    last = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )
    current = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=30,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )

    handled, _ = _maybe_apply_fast_path(tray, last_applied=last, current=current)

    assert handled is False
    tray.engine.set_brightness.assert_not_called()


def test_fastpath_brightness_change_not_taken_for_non_sw_effect(monkeypatch: pytest.MonkeyPatch) -> None:
    tray = _mk_tray(engine_running=True)

    last = ConfigApplyState(
        effect="wave",  # treated as hardware effect name
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )
    current = ConfigApplyState(
        effect="wave",
        speed=4,
        brightness=30,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )

    handled, _ = _maybe_apply_fast_path(tray, last_applied=last, current=current)

    assert handled is False
    tray.engine.set_brightness.assert_not_called()
