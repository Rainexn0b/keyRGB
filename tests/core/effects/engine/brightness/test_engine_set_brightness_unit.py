from __future__ import annotations

import logging
from threading import Event, RLock, Thread

from keyrgb.core.effects.engine_support.brightness import _EngineBrightness


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

    with caplog.at_level(logging.INFO, logger="keyrgb.core.effects.engine_brightness"):
        engine.set_brightness(20)

    info_msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert any("engine.set_brightness" in m for m in info_msgs)
    assert any("engine -> kb.set_brightness" in m for m in info_msgs)


# ---------------------------------------------------------------------------
# Replacement start_effect invalidates in-flight fades (KSW-4)
# ---------------------------------------------------------------------------


class _GateFirstAcquireLock:
    """RLock proxy that parks the first acquisition until released.

    Reproduces "a brightness commit already passed its unlocked pre-check and is
    now waiting for ``kb_lock``" deterministically. The wrapped lock is still
    free while the gate is parked, so the replacement lifecycle boundary can
    advance the fade token exactly the way ``start_effect`` does.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self.parked = Event()
        self.release = Event()
        self._gate_armed = True

    def __enter__(self) -> None:
        if self._gate_armed:
            self._gate_armed = False
            self.parked.set()
            assert self.release.wait(timeout=5.0), "gate was never released"
        self._lock.acquire()

    def __exit__(self, exc_type, exc, tb) -> bool:
        self._lock.release()
        return False


def _run_gated(engine: _TestEngine, gate: _GateFirstAcquireLock, operation) -> None:
    """Run *operation* on a worker, advance the token while it is parked."""

    worker = Thread(target=operation, daemon=True)
    worker.start()
    assert gate.parked.wait(timeout=5.0), "operation never reached a locked commit"

    # Exactly what start_effect does at its lifecycle boundary.
    engine._invalidate_brightness_fade()

    gate.release.set()
    worker.join(timeout=5.0)
    assert not worker.is_alive()


def test_stale_fade_step_does_not_commit_after_token_advance() -> None:
    """An old-token step waiting on kb_lock must write nothing once superseded."""

    engine = _TestEngine()
    engine._brightness_value = 40
    gate = _GateFirstAcquireLock()
    engine.kb_lock = gate  # type: ignore[assignment]
    token = engine._bump_brightness_fade_token()

    _run_gated(
        engine,
        gate,
        lambda: engine._fade_brightness(
            start=40,
            end=1,
            apply_to_hardware=True,
            duration_s=0.0,
            token=token,
        ),
    )

    assert engine.kb.brightness_calls == []
    assert engine._brightness_value == 40


def test_stale_turn_off_does_not_commit_terminal_off_after_token_advance() -> None:
    """A superseded fading turn_off must not blank the replacement effect."""

    engine = _TestEngine()
    engine._brightness_value = 40
    engine._device_mode_off = False
    gate = _GateFirstAcquireLock()
    engine.kb_lock = gate  # type: ignore[assignment]

    _run_gated(engine, gate, lambda: engine.turn_off(fade=True, fade_duration_s=0.0))

    assert engine.kb.brightness_calls == []
    assert engine.kb.turn_off_calls == 0
    # Neither the off write nor its mode bookkeeping may land on the new effect.
    assert engine._device_mode_off is False
    assert engine._brightness_value == 40


def test_stale_turn_off_flatten_frame_is_skipped_after_token_advance() -> None:
    """The pre-fade per-key flatten is a brightness write too — also gated."""

    engine = _TestEngine()
    engine._brightness_value = 40
    engine._device_mode_off = False
    engine.per_key_colors = {(0, 0): (255, 0, 0)}
    engine.current_color = (0, 255, 255)
    gate = _GateFirstAcquireLock()
    engine.kb_lock = gate  # type: ignore[assignment]

    color_calls: list[object] = []
    engine.kb.set_color = lambda *a, **k: color_calls.append((a, k))  # type: ignore[attr-defined]

    _run_gated(engine, gate, lambda: engine.turn_off(fade=True, fade_duration_s=0.0))

    assert color_calls == []
    assert engine.kb.turn_off_calls == 0
    assert engine._device_mode_off is False


def test_stale_set_brightness_does_not_commit_target_after_token_advance() -> None:
    """A superseded fading set_brightness must not force its target."""

    engine = _TestEngine()
    engine._brightness_value = 40
    gate = _GateFirstAcquireLock()
    engine.kb_lock = gate  # type: ignore[assignment]

    _run_gated(engine, gate, lambda: engine.set_brightness(0, fade=True, fade_duration_s=0.0))

    assert engine.kb.brightness_calls == []
    assert engine._brightness_value == 40


def test_stale_unfaded_set_brightness_does_not_commit_target_after_token_advance() -> None:
    """Without a fade the terminal target write is the only commit — still gated."""

    engine = _TestEngine()
    engine._brightness_value = 40
    gate = _GateFirstAcquireLock()
    engine.kb_lock = gate  # type: ignore[assignment]

    _run_gated(engine, gate, lambda: engine.set_brightness(10))

    assert engine.kb.brightness_calls == []
    assert engine._brightness_value == 40


def test_invalidate_brightness_fade_advances_token_under_kb_lock() -> None:
    """Token advance happens while holding kb_lock (kb_lock -> fade lock order)."""

    engine = _TestEngine()
    observed: list[bool] = []

    class _ObservingLock:
        def __init__(self) -> None:
            self._lock = RLock()
            self.held = False

        def __enter__(self) -> None:
            self._lock.acquire()
            self.held = True

        def __exit__(self, exc_type, exc, tb) -> bool:
            self.held = False
            self._lock.release()
            return False

    kb_lock = _ObservingLock()
    engine.kb_lock = kb_lock  # type: ignore[assignment]

    original_advance = engine._advance_brightness_fade_token_unlocked

    def _advance() -> int:
        observed.append(kb_lock.held)
        return original_advance()

    engine._advance_brightness_fade_token_unlocked = _advance  # type: ignore[method-assign]

    assert engine._invalidate_brightness_fade() == 1
    assert observed == [True]


def test_serialized_turn_off_and_set_brightness_still_complete() -> None:
    """No concurrent start: both operations must still commit as before."""

    engine = _TestEngine()
    engine._brightness_value = 40

    engine.set_brightness(20, fade=True, fade_duration_s=0.0)
    assert engine._brightness_value == 20
    assert engine.kb.brightness_calls[-1] == 20

    engine.turn_off(fade=True, fade_duration_s=0.0)
    assert engine._brightness_value == 0
    assert engine.kb.turn_off_calls == 1


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
