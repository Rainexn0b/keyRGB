from __future__ import annotations

import logging
from threading import RLock

import pytest

from src.core.effects.engine_support.brightness import (
    _EngineBrightness,
    _brightness_fade_token_or_default,
    _device_available_or_default,
)


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
            raise TypeError("cache write failed")  # simulates type-coercion failure in setter
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


def test_fade_brightness_propagates_unexpected_failures() -> None:
    engine = _TestEngine()
    engine._brightness_fade_token = 1

    def _boom(_brightness: int) -> None:
        raise AssertionError("unexpected brightness bug")

    engine.kb.set_brightness = _boom  # type: ignore[method-assign]

    with pytest.raises(AssertionError, match="unexpected brightness bug"):
        engine._fade_brightness(
            start=25,
            end=10,
            apply_to_hardware=True,
            duration_s=0.0,
            token=1,
        )


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


# ---------------------------------------------------------------------------
# _brightness_fade_token_or_default / _device_available_or_default
# ---------------------------------------------------------------------------


def test_brightness_fade_token_or_default_returns_default_when_attr_missing() -> None:
    engine = _TestEngine()
    del engine._brightness_fade_token
    result = _brightness_fade_token_or_default(engine, default=42)
    assert result == 42


def test_device_available_or_default_returns_default_when_attr_missing() -> None:
    engine = _TestEngine()
    del engine.device_available
    result = _device_available_or_default(engine, default=False)
    assert result is False


# ---------------------------------------------------------------------------
# _bump_brightness_fade_token — bare fallback failure (lines 65-67)
# ---------------------------------------------------------------------------


def test_bump_brightness_fade_token_bare_fallback_logs_and_returns_minus_one(caplog) -> None:
    class _BrokenAdvanceEngine(_TestEngine):
        def _advance_brightness_fade_token_unlocked(self) -> int:
            raise AttributeError("no token")

    engine = _BrokenAdvanceEngine()
    engine._brightness_fade_lock = _FailEnterLock()  # type: ignore[assignment]

    with caplog.at_level(logging.ERROR, logger="src.core.effects.engine_brightness"):
        token = engine._bump_brightness_fade_token()

    assert token == -1
    records = [r for r in caplog.records if "Failed to advance brightness fade token" in r.getMessage()]
    assert records


# ---------------------------------------------------------------------------
# _fade_brightness — edge cases
# ---------------------------------------------------------------------------


def test_fade_brightness_returns_immediately_when_start_equals_end() -> None:
    engine = _TestEngine()
    engine._brightness_value = 10
    engine._fade_brightness(start=10, end=10, apply_to_hardware=False, duration_s=0.0, token=0)
    assert engine.kb.brightness_calls == []


def test_fade_brightness_with_positive_duration_uses_multiple_steps(monkeypatch) -> None:
    """Covers the duration_s > 0 branch (choose_steps / dt calculation) and time.sleep call."""
    import src.core.effects.engine_support.brightness as _bmod

    sleep_calls: list[float] = []
    monkeypatch.setattr(_bmod.time, "sleep", sleep_calls.append)

    engine = _TestEngine()
    engine._brightness_value = 10
    engine._brightness_fade_token = 0
    engine._fade_brightness(
        start=10,
        end=20,
        apply_to_hardware=False,
        duration_s=0.1,
        token=0,
    )

    assert engine._brightness_value == 20
    assert sleep_calls  # time.sleep was invoked


def test_fade_brightness_continue_when_val_equals_start(monkeypatch) -> None:
    """First interpolation step rounds back to start → continue; second step writes."""
    import src.core.effects.engine_support.brightness as _bmod

    sleep_calls: list[float] = []
    monkeypatch.setattr(_bmod.time, "sleep", sleep_calls.append)

    engine = _TestEngine()
    engine._brightness_value = 10
    engine._brightness_fade_token = 0
    # duration_s=0.04 → choose_steps returns 2; step-1 t=0.5 → round(10.5)=10 (banker) → continue
    engine._fade_brightness(
        start=10,
        end=11,
        apply_to_hardware=False,
        duration_s=0.04,
        token=0,
    )

    assert engine._brightness_value == 11


def test_fade_brightness_exits_early_on_token_mismatch() -> None:
    engine = _TestEngine()
    engine._brightness_value = 25
    engine._brightness_fade_token = 99  # mismatch: token arg = 1
    engine._fade_brightness(
        start=25,
        end=10,
        apply_to_hardware=False,
        duration_s=0.0,
        token=1,
    )
    assert engine.kb.brightness_calls == []


def test_fade_brightness_logs_when_token_comparison_raises(caplog) -> None:
    class _NoTokenReadEngine(_TestEngine):
        @property
        def _brightness_fade_token(self) -> int:  # type: ignore[override]
            raise AttributeError("no token attr")

        @_brightness_fade_token.setter
        def _brightness_fade_token(self, value: int) -> None:
            pass  # discard writes

    engine = _NoTokenReadEngine()
    engine._brightness_value = 25

    with caplog.at_level(logging.ERROR, logger="src.core.effects.engine_brightness"):
        engine._fade_brightness(
            start=25,
            end=10,
            apply_to_hardware=False,
            duration_s=0.0,
            token=1,
        )

    records = [r for r in caplog.records if "Failed to compare brightness fade token" in r.getMessage()]
    assert records


# ---------------------------------------------------------------------------
# turn_off — fade path
# ---------------------------------------------------------------------------


def test_turn_off_with_fade_and_low_brightness_does_not_fade() -> None:
    engine = _TestEngine()
    engine._brightness_value = 1  # prev <= 1 → _fade_brightness not called
    engine.turn_off(fade=True)
    assert engine.kb.brightness_calls == []
    assert engine.kb.turn_off_calls == 1


def test_turn_off_with_fade_and_high_brightness_fades_down() -> None:
    engine = _TestEngine()
    engine._brightness_value = 25
    engine.turn_off(fade=True, fade_duration_s=0.0)
    assert engine.kb.turn_off_calls == 1
    assert any(v >= 1 for v in engine.kb.brightness_calls)
    assert engine._brightness_value == 0


# ---------------------------------------------------------------------------
# set_brightness — various paths
# ---------------------------------------------------------------------------


def test_set_brightness_basic_writes_to_hardware() -> None:
    engine = _TestEngine()
    engine._brightness_value = 0
    engine.set_brightness(30)
    assert engine._brightness_value == 30
    assert engine.kb.brightness_calls == [30]


def test_set_brightness_apply_to_hardware_false_does_not_write_kb() -> None:
    engine = _TestEngine()
    engine._brightness_value = 10
    engine.set_brightness(30, apply_to_hardware=False)
    assert engine._brightness_value == 30
    assert engine.kb.brightness_calls == []


def test_set_brightness_skips_fade_when_target_equals_prev() -> None:
    engine = _TestEngine()
    engine._brightness_value = 25
    engine.set_brightness(25, fade=True)
    # No fade, but hardware write still happens
    assert engine.kb.brightness_calls == [25]
    assert len(engine.kb.brightness_calls) == 1


def test_set_brightness_fade_to_1_then_write_0_when_target_0() -> None:
    engine = _TestEngine()
    engine._brightness_value = 25
    engine.set_brightness(0, fade=True, fade_duration_s=0.0)
    assert engine._brightness_value == 0
    assert 0 in engine.kb.brightness_calls


def test_set_brightness_logs_debug_when_env_set(monkeypatch, caplog) -> None:
    monkeypatch.setenv("KEYRGB_DEBUG_BRIGHTNESS", "1")
    engine = _TestEngine()
    engine._brightness_value = 10

    with caplog.at_level(logging.INFO, logger="src.core.effects.engine_brightness"):
        engine.set_brightness(20)

    info_msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert any("engine.set_brightness" in m for m in info_msgs)
    assert any("engine -> kb.set_brightness" in m for m in info_msgs)


def test_set_brightness_prev_reread_attr_error_inside_lock() -> None:
    """Cover the _INT_ATTR_ERRORS fallback for prev re-read inside kb_lock (lines 185-187)."""

    class _SecondReadFailEngine(_TestEngine):
        def __init__(self) -> None:
            super().__init__()
            self._read_count = 0

        @property
        def brightness(self) -> int:  # type: ignore[override]
            self._read_count += 1
            if self._read_count == 2:
                raise AttributeError("second read fails")
            return self._brightness_value

        @brightness.setter
        def brightness(self, value: int) -> None:
            if self._fail_cache_write:
                raise TypeError("cache write failed")
            self._brightness_value = int(value)

    engine = _SecondReadFailEngine()
    engine._brightness_value = 25
    engine.set_brightness(30)
    assert engine._brightness_value == 30
