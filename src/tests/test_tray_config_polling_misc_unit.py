from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

import pytest

from src.tray.pollers import config_polling
from src.tray.pollers.config_polling import (
    ConfigApplyState,
    _apply_from_config_once,
    _compute_config_apply_state,
    _maybe_apply_fast_path,
    _state_for_log,
    start_config_polling,
)


def test_compute_config_apply_state_perkey_sig_handles_unorderable_items() -> None:
    tray = MagicMock()

    # dict.items() that can't be sorted due to unorderable keys.
    tray.config = SimpleNamespace(
        effect="perkey",
        per_key_colors={1: (1, 2, 3), "x": (4, 5, 6)},
        speed=1,
        brightness=2,
        color=(7, 8, 9),
        reactive_use_manual_color=False,
        reactive_color=(10, 20, 30),
    )

    state = _compute_config_apply_state(tray)
    assert state.effect == "perkey"
    assert state.perkey_sig is None


def test_compute_config_apply_state_handles_property_exceptions() -> None:
    class _Cfg:
        effect = "rainbow_wave"
        speed = 1
        brightness = 2

        @property
        def reactive_use_manual_color(self):
            raise RuntimeError("boom")

        @property
        def reactive_color(self):
            raise RuntimeError("boom")

        @property
        def color(self):
            raise RuntimeError("boom")

        per_key_colors = {}

    tray = MagicMock()
    tray.config = _Cfg()

    state = _compute_config_apply_state(tray)
    assert state.reactive_use_manual is False
    assert state.reactive_color == (255, 255, 255)
    assert state.color == (255, 255, 255)


def test_state_for_log_returns_none_on_unexpected_state_shape() -> None:
    class _BadIterable:
        def __iter__(self):
            raise RuntimeError("boom")

    bad = ConfigApplyState(
        effect="x",
        speed=1,
        brightness=2,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(1, 2, 3),
    )

    # Bypass the type hint: assign a bad color payload.
    object.__setattr__(bad, "color", _BadIterable())

    assert _state_for_log(bad) is None


def test_maybe_apply_fast_path_handles_shape_errors_gracefully() -> None:
    tray = MagicMock()
    tray.engine = MagicMock()

    last_applied = object()  # missing expected fields
    current = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )

    handled, new_last = _maybe_apply_fast_path(tray, last_applied=last_applied, current=current)
    assert handled is False
    assert new_last == current


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
        patch.object(
            config_polling,
            "_compute_config_apply_state",
            side_effect=RuntimeError("boom"),
        ),
        patch.object(config_polling.time, "monotonic", side_effect=[100.0, 120.0, 200.0]),
    ):
        # First call should log and bump warn_at.
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

        # Second call within 60s should not log again.
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

        # Third call after 60s should log again.
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


def test_start_config_polling_runs_startup_and_mtime_reload_paths_without_threads() -> None:
    tray = _mk_tray_base(effect="wave", brightness=10)
    tray.config.reload = MagicMock()

    # Make apply_from_config_once observable but deterministic.
    with patch.object(
        config_polling,
        "_apply_from_config_once",
        wraps=config_polling._apply_from_config_once,
    ) as apply_once:
        captured = {}

        def _fake_thread(*, target, daemon):
            captured["target"] = target
            t = MagicMock()
            t.start = MagicMock()
            return t

        class _Stat:
            def __init__(self, mtime: float):
                self.st_mtime = mtime

        mtimes = [FileNotFoundError(), _Stat(1.0), _Stat(2.0), _Stat(2.0)]

        def _stat():
            v = mtimes.pop(0)
            if isinstance(v, Exception):
                raise v
            return v

        class _FakePath:
            def __init__(self, _p: str):
                pass

            def stat(self):
                return _stat()

        # Stop the infinite loop after a couple of iterations.
        sleep_calls = {"n": 0}

        def _sleep(_s: float):
            sleep_calls["n"] += 1
            if sleep_calls["n"] >= 2:
                raise StopIteration

        with (
            patch.object(config_polling, "Path", _FakePath),
            patch.object(
                config_polling.threading,
                "Thread",
                side_effect=_fake_thread,
            ),
            patch.object(config_polling.time, "sleep", side_effect=_sleep),
        ):
            start_config_polling(tray, ite_num_rows=6, ite_num_cols=21)

            # Run the poller synchronously.
            with pytest.raises(StopIteration):
                captured["target"]()

        # Should have attempted startup and at least one mtime_change apply.
        causes = [kwargs["cause"] for (_args, kwargs) in apply_once.call_args_list]
        assert "startup" in causes
        assert "mtime_change" in causes


def test_start_config_polling_logs_startup_reload_exception_throttled() -> None:
    tray = _mk_tray_base(effect="wave", brightness=10)

    tray.config.reload = MagicMock(side_effect=RuntimeError("boom"))

    captured = {}

    def _fake_thread(*, target, daemon):
        captured["target"] = target
        t = MagicMock()
        t.start = MagicMock()
        return t

    class _Stat:
        def __init__(self, mtime: float):
            self.st_mtime = mtime

    class _FakePath:
        def __init__(self, _p: str):
            pass

        def stat(self):
            return _Stat(1.0)

    def _sleep(_s: float):
        raise StopIteration

    with (
        patch.object(config_polling, "Path", _FakePath),
        patch.object(
            config_polling.threading,
            "Thread",
            side_effect=_fake_thread,
        ),
        patch.object(config_polling.time, "sleep", side_effect=_sleep),
        patch.object(
            config_polling.time,
            "monotonic",
            return_value=100.0,
        ),
    ):
        start_config_polling(tray, ite_num_rows=6, ite_num_cols=21)
        with pytest.raises(StopIteration):
            captured["target"]()

    tray._log_exception.assert_called_once()
