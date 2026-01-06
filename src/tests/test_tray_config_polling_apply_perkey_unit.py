from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from src.tray.pollers.config_polling import ConfigApplyState, _apply_from_config_once


def _mk_tray_for_perkey(*, brightness: int, base_color=(9, 8, 7), per_key_colors=None) -> MagicMock:
    tray = MagicMock()
    tray.is_off = False
    tray._user_forced_off = False
    tray._power_forced_off = False
    tray._idle_forced_off = False

    tray.config = SimpleNamespace(
        effect="perkey",
        speed=4,
        brightness=brightness,
        color=base_color,
        per_key_colors=per_key_colors or {},
        reactive_use_manual_color=False,
        reactive_color=(10, 20, 30),
    )

    tray.engine = MagicMock()
    tray.engine.running = True
    tray.engine.kb = MagicMock()

    # Context-manager lock used by perkey apply.
    tray.engine.kb_lock = MagicMock(__enter__=lambda s: None, __exit__=lambda s, *args: None)

    tray._log_event = MagicMock()
    tray._refresh_ui = MagicMock()
    tray._update_menu = MagicMock()
    tray._start_current_effect = MagicMock()

    return tray


def test_config_polling_apply_perkey_fills_partial_map_to_full_matrix() -> None:
    tray = _mk_tray_for_perkey(
        brightness=50,
        base_color=(1, 2, 3),
        per_key_colors={
            (0, 0): (255, 0, 0),
            (1, 1): (0, 255, 0),
        },
    )

    last_applied = ConfigApplyState(
        effect="perkey",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )

    _apply_from_config_once(
        tray,
        ite_num_rows=2,
        ite_num_cols=3,
        cause="mtime_change",
        last_applied=last_applied,
        last_apply_warn_at=0.0,
    )

    tray.engine.stop.assert_called_once()
    tray._start_current_effect.assert_not_called()

    # Ensure we filled all 2x3 positions.
    (colors_arg,), kwargs = tray.engine.kb.set_key_colors.call_args
    assert kwargs["brightness"] == 50
    assert kwargs["enable_user_mode"] is True

    assert len(colors_arg) == 6
    assert colors_arg[(0, 0)] == (255, 0, 0)
    assert colors_arg[(1, 1)] == (0, 255, 0)

    # Filled positions should use base color.
    for coord in [(0, 1), (0, 2), (1, 0), (1, 2)]:
        assert colors_arg[coord] == (1, 2, 3)


def test_config_polling_apply_perkey_does_not_fill_when_map_empty() -> None:
    tray = _mk_tray_for_perkey(brightness=50, base_color=(1, 2, 3), per_key_colors={})

    last_applied = ConfigApplyState(
        effect="perkey",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )

    _apply_from_config_once(
        tray,
        ite_num_rows=2,
        ite_num_cols=3,
        cause="mtime_change",
        last_applied=last_applied,
        last_apply_warn_at=0.0,
    )

    (colors_arg,), _ = tray.engine.kb.set_key_colors.call_args
    assert colors_arg == {}
