from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.tray.pollers import config_polling
from src.tray.pollers.config_polling import start_config_polling


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


def test_start_config_polling_runs_startup_and_mtime_reload_paths_without_threads() -> None:
    tray = _mk_tray_base(effect="wave", brightness=10)
    tray.config.reload = MagicMock()

    with patch.object(
        config_polling, "_apply_from_config_once", wraps=config_polling._apply_from_config_once
    ) as apply_once:
        captured: dict[str, object] = {}

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
            value = mtimes.pop(0)
            if isinstance(value, Exception):
                raise value
            return value

        class _FakePath:
            def __init__(self, _path: str):
                pass

            def stat(self):
                return _stat()

            def read_bytes(self) -> bytes:
                return b"changed"

        sleep_calls = {"n": 0}

        def _sleep(_seconds: float):
            sleep_calls["n"] += 1
            if sleep_calls["n"] >= 2:
                raise StopIteration

        with (
            patch.object(config_polling, "Path", _FakePath),
            patch.object(config_polling.threading, "Thread", side_effect=_fake_thread),
            patch.object(config_polling.time, "sleep", side_effect=_sleep),
        ):
            start_config_polling(tray, ite_num_rows=6, ite_num_cols=21)

            with pytest.raises(StopIteration):
                captured["target"]()

        causes = [kwargs["cause"] for (_args, kwargs) in apply_once.call_args_list]
        assert "startup" in causes
        assert "mtime_change" in causes


def test_start_config_polling_logs_startup_reload_exception_throttled() -> None:
    tray = _mk_tray_base(effect="wave", brightness=10)
    tray.config.reload = MagicMock(side_effect=RuntimeError("boom"))

    captured: dict[str, object] = {}

    def _fake_thread(*, target, daemon):
        captured["target"] = target
        t = MagicMock()
        t.start = MagicMock()
        return t

    class _Stat:
        def __init__(self, mtime: float):
            self.st_mtime = mtime

    class _FakePath:
        def __init__(self, _path: str):
            pass

        def stat(self):
            return _Stat(1.0)

        def read_bytes(self) -> bytes:
            return b"startup"

    def _sleep(_seconds: float):
        raise StopIteration

    with (
        patch.object(config_polling, "Path", _FakePath),
        patch.object(config_polling.threading, "Thread", side_effect=_fake_thread),
        patch.object(config_polling.time, "sleep", side_effect=_sleep),
        patch.object(config_polling.time, "monotonic", return_value=100.0),
    ):
        start_config_polling(tray, ite_num_rows=6, ite_num_cols=21)
        with pytest.raises(StopIteration):
            captured["target"]()

    tray._log_exception.assert_called_once()


def test_start_config_polling_survives_reload_log_failures() -> None:
    tray = _mk_tray_base(effect="wave", brightness=10)
    tray.config.reload = MagicMock(side_effect=[None, RuntimeError("reload boom")])
    tray._log_exception = MagicMock(side_effect=RuntimeError("logger boom"))

    captured: dict[str, object] = {}

    def _fake_thread(*, target, daemon):
        captured["target"] = target
        t = MagicMock()
        t.start = MagicMock()
        return t

    class _Stat:
        def __init__(self, mtime: float):
            self.st_mtime = mtime

    mtimes = [FileNotFoundError(), _Stat(1.0)]

    def _stat():
        value = mtimes.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    class _FakePath:
        def __init__(self, _path: str):
            pass

        def stat(self):
            return _stat()

        def read_bytes(self) -> bytes:
            return b"changed"

    def _sleep(_seconds: float):
        raise StopIteration

    with (
        patch.object(config_polling, "Path", _FakePath),
        patch.object(config_polling.threading, "Thread", side_effect=_fake_thread),
        patch.object(config_polling.time, "sleep", side_effect=_sleep),
    ):
        start_config_polling(tray, ite_num_rows=6, ite_num_cols=21)
        with pytest.raises(StopIteration):
            captured["target"]()

    assert tray.config.reload.call_count == 2
    tray._log_exception.assert_called_once()
