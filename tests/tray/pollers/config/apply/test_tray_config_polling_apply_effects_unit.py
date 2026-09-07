from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

import pytest

from keyrgb.tray.pollers import config_polling
from keyrgb.tray.pollers.config_polling import ConfigApplyState, _apply_from_config_once


def _mk_tray_base(*, effect: str, brightness: int) -> MagicMock:
    from tests.tray.fakes import make_owner_backed_mock_tray

    tray = make_owner_backed_mock_tray(
        is_off=False,
        user_forced_off=False,
        power_forced_off=False,
        idle_forced_off=False,
    )
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
    tray.engine.running = True
    tray.engine.kb = MagicMock()
    tray.engine.kb_lock = MagicMock(__enter__=lambda s: None, __exit__=lambda s, *args: None)
    return tray


def test_apply_from_config_once_perkey_enable_user_mode_typeerror_fallback() -> None:
    tray = _mk_tray_base(effect="perkey", brightness=10)
    tray.config.per_key_colors = {(0, 0): (9, 9, 9)}

    calls = {"with_save": 0, "without_save": 0}

    def enable_user_mode(*, brightness: int, save: bool = False):
        if save is True:
            calls["with_save"] += 1
            raise TypeError("save not supported")
        calls["without_save"] += 1

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


def test_apply_from_config_once_perkey_enable_user_mode_runtimeerror_is_logged() -> None:
    tray = _mk_tray_base(effect="perkey", brightness=10)
    tray.config.per_key_colors = {(0, 0): (9, 9, 9)}
    tray.engine.kb.enable_user_mode = MagicMock(side_effect=RuntimeError("boom"))

    _apply_from_config_once(
        tray,
        ite_num_rows=1,
        ite_num_cols=1,
        cause="mtime_change",
        last_applied=None,
        last_apply_warn_at=0.0,
    )

    tray._log_exception.assert_any_call("Failed to enable per-key user mode: %s", ANY)
    tray.engine.kb.set_key_colors.assert_called_once()


def test_apply_from_config_once_uniform_effect_sets_color() -> None:
    tray = _mk_tray_base(effect="none", brightness=10)
    tray.is_off = True

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
    assert tray.is_off is False


def test_apply_from_config_once_other_effect_starts_current_effect() -> None:
    tray = _mk_tray_base(effect="wave", brightness=10)

    _apply_from_config_once(
        tray,
        ite_num_rows=6,
        ite_num_cols=21,
        cause="mtime_change",
        last_applied=None,
        last_apply_warn_at=0.0,
    )

    tray._start_current_effect.assert_called_once()


def test_apply_effect_requests_atomic_brightness_preservation() -> None:
    """The brightness_guard dips the keyboard (40→8→16→24→32→40) if
    ``_last_rendered_brightness`` is cleared to None by ``engine.stop()``
    during a config-apply restart.  This test verifies the value is preserved.
    """

    tray = _mk_tray_base(effect="wave", brightness=40)
    _apply_from_config_once(
        tray,
        ite_num_rows=6,
        ite_num_cols=21,
        cause="startup",
        last_applied=None,
        last_apply_warn_at=0.0,
    )

    tray._start_current_effect.assert_called_once_with(preserve_last_rendered_brightness=True)


def test_startup_apply_skips_restart_when_autostarted_loop_effect_is_running() -> None:
    tray = _mk_tray_base(effect="reactive_ripple", brightness=40)
    tray.engine.current_effect = "reactive_ripple"

    new_last, warn_at = _apply_from_config_once(
        tray,
        ite_num_rows=6,
        ite_num_cols=21,
        cause="startup",
        last_applied=None,
        last_apply_warn_at=0.0,
    )

    assert isinstance(new_last, ConfigApplyState)
    assert new_last.effect == "reactive_ripple"
    assert warn_at == 0.0
    tray._start_current_effect.assert_not_called()


def test_startup_apply_restarts_when_running_effect_differs_from_config() -> None:
    tray = _mk_tray_base(effect="reactive_ripple", brightness=40)
    tray.engine.current_effect = "rainbow_wave"

    _apply_from_config_once(
        tray,
        ite_num_rows=6,
        ite_num_cols=21,
        cause="startup",
        last_applied=None,
        last_apply_warn_at=0.0,
    )

    tray._start_current_effect.assert_called_once_with(preserve_last_rendered_brightness=True)


def test_apply_from_config_once_logs_recoverable_apply_error() -> None:
    tray = _mk_tray_base(effect="wave", brightness=10)
    tray._start_current_effect.side_effect = RuntimeError("apply boom")

    _apply_from_config_once(
        tray,
        ite_num_rows=6,
        ite_num_cols=21,
        cause="mtime_change",
        last_applied=None,
        last_apply_warn_at=0.0,
    )

    tray._log_exception.assert_any_call("Error applying config change: %s", ANY)


def test_apply_from_config_once_propagates_unexpected_apply_error() -> None:
    tray = _mk_tray_base(effect="wave", brightness=10)
    tray._start_current_effect.side_effect = AssertionError("unexpected apply bug")

    with pytest.raises(AssertionError, match="unexpected apply bug"):
        _apply_from_config_once(
            tray,
            ite_num_rows=6,
            ite_num_cols=21,
            cause="mtime_change",
            last_applied=None,
            last_apply_warn_at=0.0,
        )


def test_apply_from_config_once_normalizes_effect_name_against_backend() -> None:
    tray = _mk_tray_base(effect="hw:rainbow_wave", brightness=10)

    backend = MagicMock()
    backend.effects.return_value = {"rainbow_wave": object()}
    tray.backend = backend

    _apply_from_config_once(
        tray,
        ite_num_rows=6,
        ite_num_cols=21,
        cause="mtime_change",
        last_applied=None,
        last_apply_warn_at=0.0,
    )

    assert tray.config.effect == "rainbow_wave"


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


def test_apply_from_config_once_propagates_unexpected_mark_device_unavailable_error() -> None:
    tray = _mk_tray_base(effect="none", brightness=10)

    err = OSError("no such")
    err.errno = 19
    tray.engine.kb.set_color = MagicMock(side_effect=err)
    tray.engine.mark_device_unavailable.side_effect = AssertionError("unexpected mark bug")

    with pytest.raises(AssertionError, match="unexpected mark bug"):
        _apply_from_config_once(
            tray,
            ite_num_rows=6,
            ite_num_cols=21,
            cause="mtime_change",
            last_applied=None,
            last_apply_warn_at=0.0,
        )


def test_apply_from_config_once_logs_fast_path_exception_and_falls_back() -> None:
    tray = _mk_tray_base(effect="none", brightness=10)

    with (
        patch.object(config_polling, "_maybe_apply_fast_path", side_effect=RuntimeError("boom")),
        patch.object(config_polling.time, "monotonic", return_value=100.0),
    ):
        new_last, warn_at = _apply_from_config_once(
            tray,
            ite_num_rows=6,
            ite_num_cols=21,
            cause="mtime_change",
            last_applied=None,
            last_apply_warn_at=0.0,
        )

    assert isinstance(new_last, ConfigApplyState)
    assert warn_at == 100.0
    tray._log_exception.assert_any_call("Error applying config fast path: %s", ANY)
    tray.engine.kb.set_color.assert_called_once_with((1, 2, 3), brightness=10)


def test_apply_from_config_once_logs_refresh_ui_exception_throttled() -> None:
    tray = _mk_tray_base(effect="none", brightness=10)
    tray._refresh_ui.side_effect = RuntimeError("boom")

    with patch.object(
        config_polling.time,
        "monotonic",
        side_effect=[100.0, 100.0, 110.0, 120.0, 190.0, 200.0],
    ):
        _, warn_at = _apply_from_config_once(
            tray,
            ite_num_rows=6,
            ite_num_cols=21,
            cause="mtime_change",
            last_applied=None,
            last_apply_warn_at=0.0,
        )
        assert warn_at == 100.0

        _, warn_at = _apply_from_config_once(
            tray,
            ite_num_rows=6,
            ite_num_cols=21,
            cause="mtime_change",
            last_applied=None,
            last_apply_warn_at=warn_at,
        )
        assert warn_at == 100.0

        _, warn_at = _apply_from_config_once(
            tray,
            ite_num_rows=6,
            ite_num_cols=21,
            cause="mtime_change",
            last_applied=None,
            last_apply_warn_at=warn_at,
        )
        assert warn_at == 200.0

    refresh_logs = [
        call_args
        for call_args in tray._log_exception.call_args_list
        if call_args.args and call_args.args[0] == "Failed to refresh tray UI after config apply: %s"
    ]
    assert len(refresh_logs) == 2


def test_apply_from_config_once_propagates_unexpected_refresh_ui_error() -> None:
    tray = _mk_tray_base(effect="none", brightness=10)
    tray._refresh_ui.side_effect = AssertionError("unexpected refresh bug")

    with pytest.raises(AssertionError, match="unexpected refresh bug"):
        _apply_from_config_once(
            tray,
            ite_num_rows=6,
            ite_num_cols=21,
            cause="mtime_change",
            last_applied=None,
            last_apply_warn_at=0.0,
        )
