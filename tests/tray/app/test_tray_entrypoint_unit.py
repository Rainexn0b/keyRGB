import pytest

import src.tray.entrypoint as entry


def test_main_happy_path_wires_startup_and_runs(monkeypatch):
    calls = {
        "logging": 0,
        "diagnostics": 0,
        "lock": 0,
        "tray_ctor": 0,
        "tray_run": 0,
        "exit": [],
    }

    monkeypatch.setattr(
        entry,
        "configure_logging",
        lambda: calls.__setitem__("logging", calls["logging"] + 1),
    )
    monkeypatch.setattr(
        entry,
        "log_startup_diagnostics_if_debug",
        lambda: calls.__setitem__("diagnostics", calls["diagnostics"] + 1),
    )
    monkeypatch.setattr(
        entry,
        "acquire_single_instance_or_exit",
        lambda: calls.__setitem__("lock", calls["lock"] + 1),
    )

    class _Tray:
        def __init__(self):
            calls["tray_ctor"] += 1

        def run(self):
            calls["tray_run"] += 1

    monkeypatch.setattr(entry, "KeyRGBTray", _Tray)
    monkeypatch.setattr(entry.sys, "exit", lambda code: calls["exit"].append(code))

    entry.main()

    assert calls == {
        "logging": 1,
        "diagnostics": 1,
        "lock": 1,
        "tray_ctor": 1,
        "tray_run": 1,
        "exit": [],
    }


def test_main_keyboard_interrupt_exits_0(monkeypatch):
    calls = {"info": 0, "exit": []}

    monkeypatch.setattr(entry, "configure_logging", lambda: None)
    monkeypatch.setattr(entry, "log_startup_diagnostics_if_debug", lambda: None)

    def _lock():
        raise KeyboardInterrupt()

    monkeypatch.setattr(entry, "acquire_single_instance_or_exit", _lock)
    monkeypatch.setattr(
        entry.logger,
        "info",
        lambda *_a, **_k: calls.__setitem__("info", calls["info"] + 1),
    )
    monkeypatch.setattr(entry.sys, "exit", lambda code: calls["exit"].append(code))

    entry.main()

    assert calls["info"] == 1
    assert calls["exit"] == [0]


def test_main_unhandled_exception_exits_1_and_logs(monkeypatch):
    calls = {"exc": 0, "exit": []}

    def _boom():
        raise RuntimeError("fail")

    monkeypatch.setattr(entry, "configure_logging", _boom)
    monkeypatch.setattr(
        entry.logger,
        "exception",
        lambda *_a, **_k: calls.__setitem__("exc", calls["exc"] + 1),
    )
    monkeypatch.setattr(entry.sys, "exit", lambda code: calls["exit"].append(code))

    entry.main()

    assert calls["exc"] == 1
    assert calls["exit"] == [1]


def test_main_propagates_unexpected_startup_bug(monkeypatch):
    def _boom():
        raise AssertionError("unexpected startup bug")

    monkeypatch.setattr(entry, "configure_logging", _boom)

    with pytest.raises(AssertionError, match="unexpected startup bug"):
        entry.main()


# ---------------------------------------------------------------------------
# Engine cleanup on shutdown (libusb teardown race fix)
# ---------------------------------------------------------------------------


def test_shutdown_engine_best_effort_no_op_when_app_is_none() -> None:
    """No crash when app was never created (early KeyboardInterrupt)."""

    entry._shutdown_engine_best_effort(None)


def test_shutdown_engine_best_effort_no_op_when_no_engine() -> None:
    """No crash when app exists but has no engine attribute."""

    class _App:
        pass

    entry._shutdown_engine_best_effort(_App())


def test_shutdown_engine_best_effort_calls_engine_close() -> None:
    """On a normal app, engine.close() is called to stop the render thread
    and release the USB device before process exit."""

    close_calls: list[bool] = []

    class _Engine:
        def close(self) -> None:
            close_calls.append(True)

    class _App:
        def __init__(self) -> None:
            self.engine = _Engine()

    entry._shutdown_engine_best_effort(_App())

    assert close_calls == [True]


def test_main_keyboard_interrupt_closes_engine_when_app_exists(monkeypatch):
    """Ctrl-C after the tray is running must stop the engine before exit.

    Without this, the reactive render thread races with libusb teardown,
    causing usbi_mutex_destroy assertion failures (core dump).
    """

    close_calls: list[bool] = []

    class _Engine:
        def close(self) -> None:
            close_calls.append(True)

    class _Tray:
        def __init__(self) -> None:
            self.engine = _Engine()

        def run(self) -> None:
            raise KeyboardInterrupt()

    monkeypatch.setattr(entry, "configure_logging", lambda: None)
    monkeypatch.setattr(entry, "log_startup_diagnostics_if_debug", lambda: None)
    monkeypatch.setattr(entry, "acquire_single_instance_or_exit", lambda: None)
    monkeypatch.setattr(entry, "KeyRGBTray", _Tray)
    monkeypatch.setattr(entry.signal, "signal", lambda *_a, **_k: None)
    monkeypatch.setattr(entry.sys, "exit", lambda code: None)

    entry.main()

    assert close_calls == [True]


def test_main_pystray_swallows_interrupt_still_closes_engine(monkeypatch):
    """When pystray catches KeyboardInterrupt internally and run() returns
    normally, the engine must still be closed via the finally block.

    This is the actual production Ctrl-C path: pystray's ``icon.run()``
    catches ``KeyboardInterrupt``, logs it, and returns. Without a ``finally``
    block, the engine is never closed and libusb crashes on interpreter exit.
    """

    close_calls: list[bool] = []

    class _Engine:
        def close(self) -> None:
            close_calls.append(True)

    class _Tray:
        def __init__(self) -> None:
            self.engine = _Engine()

        def run(self) -> None:
            # Pystray swallows KeyboardInterrupt and returns normally.
            pass

    monkeypatch.setattr(entry, "configure_logging", lambda: None)
    monkeypatch.setattr(entry, "log_startup_diagnostics_if_debug", lambda: None)
    monkeypatch.setattr(entry, "acquire_single_instance_or_exit", lambda: None)
    monkeypatch.setattr(entry, "KeyRGBTray", _Tray)
    monkeypatch.setattr(entry.signal, "signal", lambda *_a, **_k: None)

    entry.main()

    assert close_calls == [True]


def test_main_system_exit_closes_engine(monkeypatch):
    """SIGTERM (raises SystemExit) must also close the engine before exit."""

    close_calls: list[bool] = []

    class _Engine:
        def close(self) -> None:
            close_calls.append(True)

    class _Tray:
        def __init__(self) -> None:
            self.engine = _Engine()

        def run(self) -> None:
            raise SystemExit(143)

    monkeypatch.setattr(entry, "configure_logging", lambda: None)
    monkeypatch.setattr(entry, "log_startup_diagnostics_if_debug", lambda: None)
    monkeypatch.setattr(entry, "acquire_single_instance_or_exit", lambda: None)
    monkeypatch.setattr(entry, "KeyRGBTray", _Tray)
    monkeypatch.setattr(entry.signal, "signal", lambda *_a, **_k: None)

    with pytest.raises(SystemExit):
        entry.main()

    assert close_calls == [True]
