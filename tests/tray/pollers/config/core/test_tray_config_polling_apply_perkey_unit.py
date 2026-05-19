from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch

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

    tray.engine.stop.assert_not_called()
    tray._start_current_effect.assert_not_called()

    # Ensure we filled all 2x3 positions.
    (colors_arg,), kwargs = tray.engine.kb.set_key_colors.call_args
    assert kwargs["brightness"] == 50
    assert kwargs["enable_user_mode"] is False

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
    assert colors_arg is tray.config.per_key_colors


def test_config_polling_apply_perkey_reuses_full_map_without_clone() -> None:
    full_map = {
        (0, 0): (1, 1, 1),
        (0, 1): (2, 2, 2),
        (0, 2): (3, 3, 3),
        (1, 0): (4, 4, 4),
        (1, 1): (5, 5, 5),
        (1, 2): (6, 6, 6),
    }
    tray = _mk_tray_for_perkey(brightness=50, base_color=(9, 8, 7), per_key_colors=full_map)

    last_applied = ConfigApplyState(
        effect="perkey",
        speed=4,
        brightness=25,
        color=(9, 8, 7),
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

    (colors_arg,), kwargs = tray.engine.kb.set_key_colors.call_args
    assert kwargs["brightness"] == 50
    assert kwargs["enable_user_mode"] is False
    assert colors_arg == full_map
    assert colors_arg is tray.config.per_key_colors


def test_config_polling_apply_perkey_syncs_layered_perkey_brightness_state() -> None:
    tray = _mk_tray_for_perkey(
        brightness=50,
        base_color=(1, 2, 3),
        per_key_colors={(0, 0): (255, 0, 0)},
    )
    tray.config.perkey_brightness = 15
    tray.engine.per_key_brightness = 15

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
        ite_num_rows=1,
        ite_num_cols=1,
        cause="mtime_change",
        last_applied=last_applied,
        last_apply_warn_at=0.0,
    )

    assert tray.config.perkey_brightness == 50
    assert tray.engine.per_key_brightness == 50
    (_colors_arg,), kwargs = tray.engine.kb.set_key_colors.call_args
    assert kwargs["brightness"] == 50


def test_config_polling_apply_perkey_clears_off_state_after_successful_apply() -> None:
    tray = _mk_tray_for_perkey(
        brightness=30,
        base_color=(1, 2, 3),
        per_key_colors={(0, 0): (255, 0, 0)},
    )
    tray.is_off = True

    _apply_from_config_once(
        tray,
        ite_num_rows=1,
        ite_num_cols=1,
        cause="mtime_change",
        last_applied=None,
        last_apply_warn_at=0.0,
    )

    assert tray.is_off is False
    tray.engine.kb.set_key_colors.assert_called_once()


def test_config_polling_apply_perkey_reasserts_user_mode_on_initial_apply() -> None:
    tray = _mk_tray_for_perkey(
        brightness=30,
        base_color=(1, 2, 3),
        per_key_colors={(0, 0): (255, 0, 0)},
    )

    _apply_from_config_once(
        tray,
        ite_num_rows=1,
        ite_num_cols=1,
        cause="startup",
        last_applied=None,
        last_apply_warn_at=0.0,
    )

    tray.engine.stop.assert_called_once()
    (_colors_arg,), kwargs = tray.engine.kb.set_key_colors.call_args
    assert kwargs["enable_user_mode"] is True


def test_config_polling_apply_perkey_reasserts_when_backend_requires_it() -> None:
    tray = _mk_tray_for_perkey(
        brightness=30,
        base_color=(1, 2, 3),
        per_key_colors={(0, 0): (255, 0, 0)},
    )
    tray.engine.kb.keyrgb_per_key_mode_policy = "reassert_every_frame"

    last_applied = ConfigApplyState(
        effect="perkey",
        speed=4,
        brightness=30,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )

    _apply_from_config_once(
        tray,
        ite_num_rows=1,
        ite_num_cols=1,
        cause="mtime_change",
        last_applied=last_applied,
        last_apply_warn_at=0.0,
    )

    tray.engine.stop.assert_called_once()
    tray.engine.kb.enable_user_mode.assert_not_called()
    (_colors_arg,), kwargs = tray.engine.kb.set_key_colors.call_args
    assert kwargs["enable_user_mode"] is True


def test_config_polling_apply_perkey_reuses_hidden_blank_without_user_mode_reassert() -> None:
    tray = _mk_tray_for_perkey(
        brightness=30,
        base_color=(1, 2, 3),
        per_key_colors={(0, 0): (255, 0, 0)},
    )
    tray.engine.kb.keyrgb_per_key_mode_policy = "reassert_every_frame"
    tray.engine.kb.get_brightness = MagicMock(return_value=0)
    tray.engine.kb.is_off = MagicMock(return_value=False)
    tray.engine.kb.set_brightness = MagicMock()

    last_applied = ConfigApplyState(
        effect="perkey",
        speed=4,
        brightness=30,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )

    _apply_from_config_once(
        tray,
        ite_num_rows=1,
        ite_num_cols=1,
        cause="mtime_change",
        last_applied=last_applied,
        last_apply_warn_at=0.0,
    )

    tray.engine.stop.assert_not_called()
    tray.engine.kb.enable_user_mode.assert_not_called()
    (_colors_arg,), kwargs = tray.engine.kb.set_key_colors.call_args
    assert kwargs["enable_user_mode"] is False
    tray.engine.kb.set_brightness.assert_called_once_with(30)


def test_config_polling_skips_recent_power_source_mtime_reapply() -> None:
    tray = _mk_tray_for_perkey(
        brightness=30,
        base_color=(1, 2, 3),
        per_key_colors={(0, 0): (255, 0, 0)},
    )
    tray._last_power_source_transition_at = 99.0

    last_applied = ConfigApplyState(
        effect="perkey",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )

    with patch("src.tray.pollers.config_polling.time.monotonic", return_value=100.0):
        new_last_applied, last_warn_at = _apply_from_config_once(
            tray,
            ite_num_rows=1,
            ite_num_cols=1,
            cause="mtime_change",
            last_applied=last_applied,
            last_apply_warn_at=0.0,
        )

    tray.engine.stop.assert_not_called()
    tray.engine.kb.set_key_colors.assert_not_called()
    tray._refresh_ui.assert_not_called()
    assert new_last_applied is not None
    assert new_last_applied.effect == "perkey"
    assert new_last_applied.brightness == 30
    assert last_warn_at == 0.0
