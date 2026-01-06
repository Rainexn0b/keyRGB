from __future__ import annotations

from types import SimpleNamespace

from src.tray.pollers import hardware_polling


class Errno19(Exception):
    def __init__(self, message: str = "boom"):
        super().__init__(message)
        self.errno = 19


def test_handle_hardware_polling_exception_errno19_marks_unavailable(monkeypatch):
    calls = {"mark": 0, "log": 0}

    tray = SimpleNamespace(
        engine=SimpleNamespace(mark_device_unavailable=lambda: calls.__setitem__("mark", calls["mark"] + 1)),
        _log_exception=lambda *a, **k: calls.__setitem__("log", calls["log"] + 1),
    )

    last = hardware_polling._handle_hardware_polling_exception(tray, Errno19(), last_error_at=123.0)

    assert calls["mark"] == 1
    assert calls["log"] == 0
    assert last == 123.0


def test_handle_hardware_polling_exception_no_such_device_marks_unavailable():
    calls = {"mark": 0}

    tray = SimpleNamespace(
        engine=SimpleNamespace(mark_device_unavailable=lambda: calls.__setitem__("mark", calls["mark"] + 1)),
        _log_exception=lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not log")),
    )

    exc = RuntimeError("No such device")
    last = hardware_polling._handle_hardware_polling_exception(tray, exc, last_error_at=1.0)

    assert calls["mark"] == 1
    assert last == 1.0


def test_handle_hardware_polling_exception_log_throttled(monkeypatch):
    calls = {"log": 0}

    tray = SimpleNamespace(
        engine=SimpleNamespace(mark_device_unavailable=lambda: (_ for _ in ()).throw(AssertionError("no"))),
        _log_exception=lambda *a, **k: calls.__setitem__("log", calls["log"] + 1),
    )

    monkeypatch.setattr(hardware_polling.time, "monotonic", lambda: 100.0)

    # Not enough time elapsed -> no log
    last = hardware_polling._handle_hardware_polling_exception(tray, RuntimeError("x"), last_error_at=90.1)
    assert calls["log"] == 0
    assert last == 90.1

    # Enough time elapsed -> log + last_error_at updated
    last = hardware_polling._handle_hardware_polling_exception(tray, RuntimeError("x"), last_error_at=60.0)
    assert calls["log"] == 1
    assert last == 100.0


def test_handle_hardware_polling_exception_swallow_log_exceptions(monkeypatch):
    tray = SimpleNamespace(
        engine=SimpleNamespace(mark_device_unavailable=lambda: None),
        _log_exception=lambda *a, **k: (_ for _ in ()).throw(OSError("bad")),
    )

    monkeypatch.setattr(hardware_polling.time, "monotonic", lambda: 200.0)

    last = hardware_polling._handle_hardware_polling_exception(tray, RuntimeError("x"), last_error_at=0.0)
    assert last == 200.0
