from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.tray.pollers.config_polling import ConfigApplyState, _apply_from_config_once


def _mk_tray(*, brightness: int, effect: str = "rainbow_wave") -> MagicMock:
    tray = MagicMock()
    tray.is_off = False
    tray._user_forced_off = False
    tray._power_forced_off = False
    tray._idle_forced_off = False

    tray.engine = MagicMock()
    tray.engine.running = True

    tray.config = SimpleNamespace(
        effect=effect,
        speed=4,
        brightness=brightness,
        color=(1, 2, 3),
        per_key_colors={},
        reactive_use_manual_color=False,
        reactive_color=(10, 20, 30),
    )

    tray._log_event = MagicMock()
    tray._update_menu = MagicMock()
    tray._refresh_ui = MagicMock()
    tray._start_current_effect = MagicMock()

    return tray


@pytest.mark.parametrize("flag_name", ["_user_forced_off", "_power_forced_off", "_idle_forced_off"])
def test_forced_off_skip_prevents_fastpath_brightness_update(flag_name: str) -> None:
    tray = _mk_tray(brightness=30, effect="rainbow_wave")
    tray.is_off = True
    setattr(tray, flag_name, True)

    last_applied = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )

    new_last_applied, new_warn_at = _apply_from_config_once(
        tray,
        ite_num_rows=6,
        ite_num_cols=21,
        cause="mtime_change",
        last_applied=last_applied,
        last_apply_warn_at=0.0,
    )

    assert isinstance(new_last_applied, ConfigApplyState)
    assert new_last_applied.brightness == 30
    assert new_warn_at == 0.0

    tray.engine.set_brightness.assert_not_called()
    tray._start_current_effect.assert_not_called()
    tray.engine.stop.assert_not_called()
    tray._refresh_ui.assert_not_called()

    tray._update_menu.assert_called_once()

    # Non-brittle: ensure we emitted the forced-off skip event.
    tray._log_event.assert_any_call(
        "config",
        "skipped_forced_off",
        cause="mtime_change",
        is_off=True,
        user_forced_off=bool(getattr(tray, "_user_forced_off", False)),
        power_forced_off=bool(getattr(tray, "_power_forced_off", False)),
        idle_forced_off=bool(getattr(tray, "_idle_forced_off", False)),
    )


def test_non_forced_off_still_allows_fastpath_brightness_update() -> None:
    tray = _mk_tray(brightness=30, effect="rainbow_wave")
    tray.is_off = False

    last_applied = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )

    new_last_applied, _ = _apply_from_config_once(
        tray,
        ite_num_rows=6,
        ite_num_cols=21,
        cause="mtime_change",
        last_applied=last_applied,
        last_apply_warn_at=0.0,
    )

    assert isinstance(new_last_applied, ConfigApplyState)
    assert new_last_applied.brightness == 30

    tray.engine.set_brightness.assert_called_once_with(30, apply_to_hardware=False)
    tray._update_menu.assert_not_called()
