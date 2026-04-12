from __future__ import annotations

import logging

import pytest

import src.gui.perkey.hardware as hardware
from src.core.resources.defaults import REFERENCE_MATRIX_COLS, REFERENCE_MATRIX_ROWS


def test_select_backend_returns_none_on_recoverable_selection_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}
    err = RuntimeError("backend boom")

    def fake_log_throttled(logger, key: str, *, interval_s: float, level: int, msg: str, exc=None) -> bool:
        seen.update(logger=logger, key=key, interval_s=interval_s, level=level, msg=msg, exc=exc)
        return True

    monkeypatch.setattr(hardware, "select_backend", lambda: (_ for _ in ()).throw(err))
    monkeypatch.setattr(hardware, "log_throttled", fake_log_throttled)

    assert hardware._select_backend() is None
    assert seen["key"] == "perkey.hardware.select_backend.failed"
    assert seen["interval_s"] == 60
    assert seen["msg"] == "Failed to select backend; disabling perkey hardware"
    assert seen["exc"] is err


def test_select_backend_propagates_unexpected_selection_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        hardware,
        "select_backend",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected backend bug")),
    )

    with pytest.raises(AssertionError, match="unexpected backend bug"):
        hardware._select_backend()


def test_backend_dimensions_or_reference_uses_reference_on_recoverable_failure() -> None:
    class BrokenBackend:
        def dimensions(self):
            raise RuntimeError("dimension boom")

    assert hardware._backend_dimensions_or_reference(BrokenBackend()) == (
        REFERENCE_MATRIX_ROWS,
        REFERENCE_MATRIX_COLS,
    )


def test_backend_dimensions_or_reference_propagates_unexpected_failure() -> None:
    class BrokenBackend:
        def dimensions(self):
            raise AssertionError("unexpected dimension bug")

    with pytest.raises(AssertionError, match="unexpected dimension bug"):
        hardware._backend_dimensions_or_reference(BrokenBackend())


def test_get_keyboard_returns_none_on_recoverable_open_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}
    err = RuntimeError("open boom")

    class BrokenBackend:
        def get_device(self):
            raise err

    def fake_log_throttled(logger, key: str, *, interval_s: float, level: int, msg: str, exc=None) -> bool:
        seen.update(logger=logger, key=key, interval_s=interval_s, level=level, msg=msg, exc=exc)
        return True

    monkeypatch.setattr(hardware, "_backend", BrokenBackend())
    monkeypatch.setattr(hardware, "log_throttled", fake_log_throttled)

    assert hardware.get_keyboard() is None
    assert seen["key"] == "perkey.hardware.get_keyboard"
    assert seen["interval_s"] == 60
    assert seen["level"] == logging.DEBUG
    assert seen["msg"] == "Failed to open keyboard device; perkey hardware unavailable"
    assert seen["exc"] is err


def test_get_keyboard_propagates_unexpected_open_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenBackend:
        def get_device(self):
            raise AssertionError("unexpected open bug")

    monkeypatch.setattr(hardware, "_backend", BrokenBackend())

    with pytest.raises(AssertionError, match="unexpected open bug"):
        hardware.get_keyboard()