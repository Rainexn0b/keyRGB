from __future__ import annotations

import logging
from threading import RLock

import pytest

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


def test_brightness_logging_proxy_tolerates_color_snapshot_failures(monkeypatch) -> None:
    monkeypatch.setenv("KEYRGB_DEBUG_BRIGHTNESS", "1")
    calls: dict[str, object] = {}

    class BrokenColor:
        def __iter__(self):
            raise RuntimeError("boom")

    class Inner:
        def set_color(self, color, *, brightness: int):
            calls["set_color"] = (color, brightness)

        def set_palette_color(self, slot: int, color) -> None:
            calls["set_palette_color"] = (slot, color)

    broken = BrokenColor()
    proxy = device._BrightnessLoggingKeyboardProxy(Inner(), logger=logging.getLogger(__name__))

    proxy.set_color(broken, brightness=17)
    proxy.set_palette_color(3, broken)

    assert calls["set_color"] == (broken, 17)
    assert calls["set_palette_color"] == (3, broken)


def test_brightness_logging_proxy_tolerates_size_snapshot_failures(monkeypatch) -> None:
    monkeypatch.setenv("KEYRGB_DEBUG_BRIGHTNESS", "1")
    calls: dict[str, object] = {}

    class BrokenSized:
        def __len__(self) -> int:
            raise RuntimeError("boom")

    class Inner:
        def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True):
            calls["set_key_colors"] = (color_map, brightness, enable_user_mode)

        def set_effect(self, effect_data) -> None:
            calls["set_effect"] = effect_data

    broken = BrokenSized()
    proxy = device._BrightnessLoggingKeyboardProxy(Inner(), logger=logging.getLogger(__name__))

    proxy.set_key_colors(broken, brightness=9, enable_user_mode=False)
    proxy.set_effect(broken)

    assert calls["set_key_colors"] == (broken, 9, False)
    assert calls["set_effect"] is broken


def test_acquire_keyboard_logs_and_falls_back_on_unexpected_error(monkeypatch) -> None:
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test::case (call)")
    monkeypatch.setenv("KEYRGB_ALLOW_HARDWARE", "1")
    seen: dict[str, object] = {}
    err = LookupError("boom")

    def fail_get():
        raise err

    def fake_log_throttled(logger, key: str, *, interval_s: float, level: int, msg: str, exc=None) -> bool:
        seen.update(
            logger=logger,
            key=key,
            interval_s=interval_s,
            level=level,
            msg=msg,
            exc=exc,
        )
        return True

    monkeypatch.setattr(device, "get", fail_get)
    monkeypatch.setattr(device, "log_throttled", fake_log_throttled)

    kb, available = acquire_keyboard(kb_lock=RLock(), logger=logging.getLogger(__name__))

    assert isinstance(kb, NullKeyboard)
    assert available is False
    assert seen["key"] == "effects.acquire_keyboard"
    assert seen["interval_s"] == 60
    assert seen["msg"] == "Failed to acquire keyboard device; falling back to NullKeyboard"
    assert seen["exc"] is err


def test_acquire_keyboard_propagates_unexpected_errors(monkeypatch) -> None:
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test::case (call)")
    monkeypatch.setenv("KEYRGB_ALLOW_HARDWARE", "1")

    def fail_get():
        raise AssertionError("unexpected acquire bug")

    monkeypatch.setattr(device, "get", fail_get)

    with pytest.raises(AssertionError, match="unexpected acquire bug"):
        acquire_keyboard(kb_lock=RLock(), logger=logging.getLogger(__name__))
