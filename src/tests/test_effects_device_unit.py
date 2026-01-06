from __future__ import annotations

import logging
from threading import RLock

import src.core.effects.device as device
from src.core.effects.device import NullKeyboard, acquire_keyboard


def test_acquire_keyboard_under_pytest_disables_hardware_by_default(
    monkeypatch,
) -> None:
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test::case (call)")
    monkeypatch.delenv("KEYRGB_ALLOW_HARDWARE", raising=False)

    def should_not_be_called():
        raise AssertionError("device.get() must not be called under pytest without opt-in")

    monkeypatch.setattr(device, "get", should_not_be_called)

    kb, available = acquire_keyboard(kb_lock=RLock(), logger=logging.getLogger(__name__))

    assert isinstance(kb, NullKeyboard)
    assert available is False


def test_acquire_keyboard_under_pytest_allows_opt_in(monkeypatch) -> None:
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test::case (call)")
    monkeypatch.setenv("KEYRGB_ALLOW_HARDWARE", "1")

    sentinel = object()
    monkeypatch.setattr(device, "get", lambda: sentinel)

    kb, available = acquire_keyboard(kb_lock=RLock(), logger=logging.getLogger(__name__))

    assert kb is sentinel
    assert available is True


def test_acquire_keyboard_under_pytest_allows_hw_tests_alias(monkeypatch) -> None:
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test::case (call)")
    monkeypatch.delenv("KEYRGB_ALLOW_HARDWARE", raising=False)
    monkeypatch.setenv("KEYRGB_HW_TESTS", "1")

    sentinel = object()
    monkeypatch.setattr(device, "get", lambda: sentinel)

    kb, available = acquire_keyboard(kb_lock=RLock(), logger=logging.getLogger(__name__))

    assert kb is sentinel
    assert available is True
