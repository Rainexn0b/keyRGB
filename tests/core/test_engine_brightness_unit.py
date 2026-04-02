from __future__ import annotations

import logging
from threading import RLock

from src.core.effects.engine_brightness import _EngineBrightness


class _SpyKeyboard:
    def __init__(self) -> None:
        self.brightness_calls: list[int] = []
        self.turn_off_calls = 0
        self.fail_set_brightness = False

    def set_brightness(self, brightness: int) -> None:
        self.brightness_calls.append(int(brightness))
        if self.fail_set_brightness:
            raise RuntimeError("device write failed")

    def turn_off(self) -> None:
        self.turn_off_calls += 1


class _TestEngine(_EngineBrightness):
    def __init__(self) -> None:
        self.kb_lock = RLock()
        self.kb = _SpyKeyboard()
        self.device_available = True
        self._brightness_value = 25
        self._fail_cache_write = False
        self.stop_calls = 0
        self._brightness_fade_token = 0
        self._brightness_fade_lock = RLock()

    @property
    def brightness(self) -> int:
        return int(self._brightness_value)

    @brightness.setter
    def brightness(self, value: int) -> None:
        if self._fail_cache_write:
            raise RuntimeError("cache write failed")
        self._brightness_value = int(value)

    def stop(self) -> None:
        self.stop_calls += 1

    def _ensure_device_available(self) -> bool:
        return True


class _FailEnterLock:
    def __enter__(self) -> None:
        raise RuntimeError("lock enter failed")

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_bump_brightness_fade_token_logs_traceback_when_lock_fails(caplog) -> None:
    engine = _TestEngine()
    engine._brightness_fade_lock = _FailEnterLock()  # type: ignore[assignment]

    with caplog.at_level(logging.ERROR, logger="src.core.effects.engine_brightness"):
        token = engine._bump_brightness_fade_token()

    assert token == 1
    assert engine._brightness_fade_token == 1

    records = [
        record
        for record in caplog.records
        if "Failed to advance brightness fade token under lock" in record.getMessage()
    ]
    assert records
    assert records[-1].exc_info is not None


def test_fade_brightness_logs_traceback_when_device_write_fails(caplog) -> None:
    engine = _TestEngine()
    engine.kb.fail_set_brightness = True
    engine._brightness_fade_token = 1

    with caplog.at_level(logging.ERROR, logger="src.core.effects.engine_brightness"):
        engine._fade_brightness(
            start=25,
            end=10,
            apply_to_hardware=True,
            duration_s=0.0,
            token=1,
        )

    assert engine.brightness == 10
    assert engine.kb.brightness_calls == [10]

    records = [record for record in caplog.records if "Brightness fade failed" in record.getMessage()]
    assert records
    assert records[-1].exc_info is not None


def test_turn_off_logs_traceback_when_cache_write_fails_but_still_turns_off(caplog) -> None:
    engine = _TestEngine()
    engine._fail_cache_write = True

    with caplog.at_level(logging.ERROR, logger="src.core.effects.engine_brightness"):
        engine.turn_off()

    assert engine.stop_calls == 1
    assert engine.kb.turn_off_calls == 1

    records = [
        record
        for record in caplog.records
        if "Failed to update engine brightness cache during turn_off" in record.getMessage()
    ]
    assert records
    assert records[-1].exc_info is not None
