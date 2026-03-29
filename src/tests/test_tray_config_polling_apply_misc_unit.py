from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

from src.tray.pollers import config_polling
from src.tray.pollers.config_polling import ConfigApplyState, _apply_from_config_once


def _mk_tray_base(*, effect: str, brightness: int) -> MagicMock:
    tray = MagicMock()
    tray.is_off = False
    tray._user_forced_off = False
    tray._power_forced_off = False
    tray._idle_forced_off = False

    tray.config = SimpleNamespace(
        CONFIG_FILE="/tmp/keyrgb-test-config.json",
        effect=effect,
        speed=4,
        brightness=brightness,
        color=(1, 2, 3),
        per_key_colors={},
        reactive_use_manual_color=False,
        reactive_color=(10, 20, 30),
    )

    tray.engine = MagicMock()
    tray.engine.running = True
    tray.engine.kb = MagicMock()
    tray.engine.kb_lock = MagicMock(__enter__=lambda s: None, __exit__=lambda s, *args: None)

    tray._log_event = MagicMock()
    tray._log_exception = MagicMock()
    tray._refresh_ui = MagicMock()
    tray._update_menu = MagicMock()
    tray._start_current_effect = MagicMock()

    return tray


def test_apply_from_config_once_returns_early_when_state_unchanged() -> None:
    tray = _mk_tray_base(effect="rainbow_wave", brightness=25)

    last_applied = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )

    new_last, warn_at = _apply_from_config_once(
        tray,
        ite_num_rows=6,
        ite_num_cols=21,
        cause="mtime_change",
        last_applied=last_applied,
        last_apply_warn_at=0.0,
    )

    assert new_last == last_applied
    assert warn_at == 0.0
    tray._start_current_effect.assert_not_called()
    tray.engine.set_brightness.assert_not_called()


def test_apply_from_config_once_logs_signature_exception_throttled() -> None:
    tray = _mk_tray_base(effect="rainbow_wave", brightness=25)

    with (
        patch.object(config_polling, "_compute_config_apply_state", side_effect=RuntimeError("boom")),
        patch.object(config_polling.time, "monotonic", side_effect=[100.0, 120.0, 200.0]),
    ):
        last, warn_at = _apply_from_config_once(
            tray,
            ite_num_rows=6,
            ite_num_cols=21,
            cause="mtime_change",
            last_applied=None,
            last_apply_warn_at=0.0,
        )
        assert warn_at == 100.0
        tray._log_exception.assert_called_once()

        tray._log_exception.reset_mock()
        last2, warn_at2 = _apply_from_config_once(
            tray,
            ite_num_rows=6,
            ite_num_cols=21,
            cause="mtime_change",
            last_applied=last,
            last_apply_warn_at=warn_at,
        )
        assert warn_at2 == 100.0
        tray._log_exception.assert_not_called()

        tray._log_exception.reset_mock()
        _apply_from_config_once(
            tray,
            ite_num_rows=6,
            ite_num_cols=21,
            cause="mtime_change",
            last_applied=last2,
            last_apply_warn_at=warn_at2,
        )
        tray._log_exception.assert_called_once()


def test_apply_from_config_once_turns_off_on_zero_brightness_and_throttles_engine_errors() -> None:
    tray = _mk_tray_base(effect="rainbow_wave", brightness=0)
    tray.engine.turn_off = MagicMock(side_effect=RuntimeError("boom"))

    with patch.object(config_polling.time, "monotonic", return_value=100.0):
        new_last, warn_at = _apply_from_config_once(
            tray,
            ite_num_rows=6,
            ite_num_cols=21,
            cause="mtime_change",
            last_applied=None,
            last_apply_warn_at=0.0,
        )

    assert isinstance(new_last, ConfigApplyState)
    assert tray.is_off is True
    assert warn_at == 100.0
    tray._log_exception.assert_any_call("Failed to turn off engine: %s", ANY)


def test_apply_from_config_once_sets_last_brightness_when_positive() -> None:
    tray = _mk_tray_base(effect="rainbow_wave", brightness=12)

    _apply_from_config_once(
        tray,
        ite_num_rows=6,
        ite_num_cols=21,
        cause="mtime_change",
        last_applied=None,
        last_apply_warn_at=0.0,
    )

    assert tray._last_brightness == 12


def test_apply_from_config_once_perkey_enable_user_mode_typeerror_fallback() -> None:
    tray = _mk_tray_base(effect="perkey", brightness=10)
    tray.config.per_key_colors = {(0, 0): (9, 9, 9)}

    calls = {"with_save": 0, "without_save": 0}

    def enable_user_mode(*, brightness: int, save: bool = False):
        if save is True:
            calls["with_save"] += 1
            raise TypeError("save not supported")
        calls["without_save"] += 1
        return None

    tray.engine.kb.enable_user_mode = enable_user_mode

    _apply_from_config_once(
        tray,
        ite_num_rows=1,
        ite_num_cols=1,
        cause="mtime_change",
        last_applied=None,
        last_apply_warn_at=0.0,
    )

    assert calls["with_save"] == 1
    assert calls["without_save"] == 1
    tray.engine.kb.set_key_colors.assert_called_once()


def test_apply_from_config_once_uniform_effect_sets_color() -> None:
    tray = _mk_tray_base(effect="none", brightness=10)

    _apply_from_config_once(
        tray,
        ite_num_rows=6,
        ite_num_cols=21,
        cause="mtime_change",
        last_applied=None,
        last_apply_warn_at=0.0,
    )

    tray.engine.stop.assert_called_once()
    tray.engine.kb.set_color.assert_called_once_with((1, 2, 3), brightness=10)


def test_apply_from_config_once_backend_exposed_effect_starts_current_effect() -> None:
    tray = _mk_tray_base(effect="wave", brightness=10)
    tray.backend.effects.return_value = {"wave": object()}

    _apply_from_config_once(
        tray,
        ite_num_rows=6,
        ite_num_cols=21,
        cause="mtime_change",
        last_applied=None,
        last_apply_warn_at=0.0,
    )

    tray._start_current_effect.assert_called_once()


def test_apply_from_config_once_unsupported_legacy_effect_falls_back_to_uniform_none() -> None:
    tray = _mk_tray_base(effect="wave", brightness=10)

    _apply_from_config_once(
        tray,
        ite_num_rows=6,
        ite_num_cols=21,
        cause="mtime_change",
        last_applied=None,
        last_apply_warn_at=0.0,
    )

    assert tray.config.effect == "none"
    tray.engine.stop.assert_called_once()
    tray.engine.kb.set_color.assert_called_once_with((1, 2, 3), brightness=10)
    tray._start_current_effect.assert_not_called()


def test_apply_from_config_once_marks_device_unavailable_on_errno_19() -> None:
    tray = _mk_tray_base(effect="none", brightness=10)

    err = OSError("no such")
    err.errno = 19
    tray.engine.kb.set_color = MagicMock(side_effect=err)

    _apply_from_config_once(
        tray,
        ite_num_rows=6,
        ite_num_cols=21,
        cause="mtime_change",
        last_applied=None,
        last_apply_warn_at=0.0,
    )

    tray.engine.mark_device_unavailable.assert_called_once()
    tray._log_exception.assert_any_call("Error applying config change: %s", ANY)
