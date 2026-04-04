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
