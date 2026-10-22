"""Deterministic shutdown interleavings with the real engine and fake devices."""

from __future__ import annotations

from threading import Event, Thread
from unittest.mock import Mock

import pytest

from keyrgb.core.effects.device import KeyboardDeviceProtocol, NullKeyboard
from keyrgb.core.effects.engine import EffectsEngine
from keyrgb.core.effects.engine_support import _start_support, core
from keyrgb.tray.controllers.runtime_coordinator import TrayRuntimeCoordinator


@pytest.fixture
def engine_device(monkeypatch):
    keyboard = Mock(spec=KeyboardDeviceProtocol)
    acquire = Mock(return_value=(keyboard, True))
    monkeypatch.setattr(core, "acquire_keyboard", acquire)
    engine = EffectsEngine()
    try:
        yield engine, keyboard, acquire
    finally:
        engine.close()


def gate_fade(engine, monkeypatch):
    entered, release = Event(), Event()
    fade = engine._fade_brightness

    def paused_fade(**kwargs):
        entered.set()
        assert release.wait(5), "fade was never released"
        return fade(**kwargs)

    monkeypatch.setattr(engine, "_fade_brightness", paused_fade)
    return entered, release


@pytest.mark.parametrize("operation", ["brightness", "off"])
def test_delayed_fade_cannot_reacquire_or_write_after_close(engine_device, monkeypatch, operation):
    engine, keyboard, acquire = engine_device
    entered, release = gate_fade(engine, monkeypatch)
    drain = engine._drain_brightness_fades
    expired_drain = Mock(side_effect=lambda _timeout: drain(0.0))
    monkeypatch.setattr(engine, "_drain_brightness_fades", expired_drain)
    with engine.defer_brightness_fades():
        future = (
            engine.set_brightness(40, fade=True, fade_duration_s=0)
            if operation == "brightness"
            else engine.turn_off(fade=True, fade_duration_s=0)
        )
    try:
        assert entered.wait(2)
        engine.close()
        expired_drain.assert_called_once_with(2.0)
        keyboard.close.assert_called_once()
    finally:
        release.set()
    assert future.result(timeout=2) is False
    assert drain(2.0)
    assert engine.device_available is False
    assert isinstance(engine.kb, NullKeyboard)
    acquire.assert_called_once()
    keyboard.set_brightness.assert_not_called()
    keyboard.turn_off.assert_not_called()


def test_close_rejects_unstarted_jobs_and_later_starts(engine_device):
    engine, keyboard, acquire = engine_device
    with engine.defer_brightness_fades():
        future = engine.set_brightness(40, fade=True)
        engine.close()
    assert future.result(timeout=2) is False
    with pytest.raises(RuntimeError, match="Effects engine is closed"):
        engine.start_effect("spectrum_cycle")
    engine.set_brightness(30)
    engine.turn_off()
    assert engine._ensure_device_available() is False
    assert engine._drain_brightness_fades(0.0)
    acquire.assert_called_once()
    keyboard.close.assert_called_once()
    keyboard.set_brightness.assert_not_called()
    keyboard.turn_off.assert_not_called()


def test_cancelled_fade_does_not_attempt_acquisition(engine_device, monkeypatch):
    engine, keyboard, _ = engine_device
    entered, release = gate_fade(engine, monkeypatch)
    ensure = Mock(wraps=engine._ensure_device_available)
    monkeypatch.setattr(engine, "_ensure_device_available", ensure)
    with engine.defer_brightness_fades():
        future = engine.set_brightness(40, fade=True, fade_duration_s=0)
    try:
        assert entered.wait(2)
        engine._invalidate_brightness_fade()
    finally:
        release.set()
    assert future.result(timeout=2) is False
    assert engine._drain_brightness_fades(2.0)
    ensure.assert_not_called()
    keyboard.set_brightness.assert_not_called()


def test_close_drains_fade_completion_without_holding_engine_locks(engine_device, monkeypatch):
    engine, keyboard, _ = engine_device
    entered, release = gate_fade(engine, monkeypatch)
    draining = Event()
    drain = engine._drain_brightness_fades
    coordinator = TrayRuntimeCoordinator()
    outcomes = []

    def observed_drain(timeout):
        draining.set()
        return drain(timeout)

    def completion(_future):
        try:
            coordinator.run(lambda: engine.start_effect("spectrum_cycle"))
        except RuntimeError as exc:
            outcomes.append(str(exc))

    monkeypatch.setattr(engine, "_drain_brightness_fades", observed_drain)
    with engine.defer_brightness_fades():
        future = engine.set_brightness(40, fade=True, fade_duration_s=0)
    future.add_done_callback(completion)
    closer = Thread(target=engine.close)
    try:
        assert entered.wait(2)
        closer.start()
        assert draining.wait(2)
    finally:
        release.set()
        closer.join(3)
        assert coordinator.stop_and_drain(timeout_s=2)
    assert not closer.is_alive()
    assert future.result(timeout=2) is False
    assert outcomes == ["Effects engine is closed"]
    assert drain(0.0)
    keyboard.close.assert_called_once()


def test_fade_drain_uses_one_deadline_for_all_workers(engine_device, monkeypatch):
    engine, _, _ = engine_device
    clock = [0.0]
    waits = []

    def join(*, timeout):
        waits.append(timeout)
        clock[0] += timeout

    workers = {Mock(spec=Thread), Mock(spec=Thread)}
    for worker in workers:
        worker.join.side_effect = join
        worker.is_alive.return_value = True
    monkeypatch.setattr(_start_support, "monotonic", lambda: clock[0])
    engine._fade_workers = workers
    try:
        assert not engine._drain_brightness_fades(2.0)
        assert waits == [2.0, 0.0]
    finally:
        engine._fade_workers = set()


def test_fade_thread_start_failure_settles_its_future(engine_device, monkeypatch):
    engine, keyboard, _ = engine_device
    worker = Mock()
    worker.start.side_effect = RuntimeError("thread start failed")
    monkeypatch.setattr(_start_support, "Thread", Mock(return_value=worker))
    with pytest.raises(RuntimeError, match="thread start failed"), engine.defer_brightness_fades():
        future = engine.set_brightness(40, fade=True)
    assert future.result(timeout=2) is False
    assert engine._drain_brightness_fades(0.0)
    keyboard.set_brightness.assert_not_called()
