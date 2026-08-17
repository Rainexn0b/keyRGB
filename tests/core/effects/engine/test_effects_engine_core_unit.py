from __future__ import annotations

import logging

import pytest

from src.core.backends.base import BackendCapabilities
from src.core.effects.engine import EffectsEngine


class _HardwareEffectsBackend:
    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            brightness=True,
            per_key=False,
            color=True,
            hardware_effects=True,
            palette=False,
        )


class _StuckEffectThread:
    def __init__(self) -> None:
        self.join_timeouts: list[float | None] = []

    def join(self, timeout: float | None = None) -> None:
        self.join_timeouts.append(timeout)

    def is_alive(self) -> bool:
        return True


def test_stop_recovers_from_malformed_thread_generation_state() -> None:
    engine = EffectsEngine()
    engine._thread_generation = "broken"  # type: ignore[assignment]
    engine._last_rendered_brightness = 25
    engine._last_hw_mode_brightness = 25
    engine.current_effect = "rainbow_wave"
    engine.stop_event.set()

    engine.stop()

    assert engine._thread_generation == 1
    assert engine._last_rendered_brightness is None
    assert engine._last_hw_mode_brightness is None
    assert engine.current_effect is None
    assert engine.stop_event.is_set() is False


def test_stop_keeps_timed_out_worker_cancelled_and_published() -> None:
    engine = EffectsEngine()
    stuck_thread = _StuckEffectThread()
    engine.running = True
    engine.thread = stuck_thread  # type: ignore[assignment]
    engine.current_effect = "rainbow_wave"

    engine.stop()

    assert engine.running is False
    assert engine.thread is stuck_thread
    assert engine.current_effect is None
    assert engine.stop_event.is_set() is True
    assert stuck_thread.join_timeouts == [2.0]


def test_start_effect_refuses_replacement_while_previous_worker_is_alive() -> None:
    engine = EffectsEngine()
    stuck_thread = _StuckEffectThread()
    engine.running = True
    engine.thread = stuck_thread  # type: ignore[assignment]
    engine.current_effect = "rainbow_wave"

    with pytest.raises(RuntimeError, match="Previous effect thread is still stopping"):
        engine.start_effect("spectrum_cycle")

    assert engine.running is False
    assert engine.thread is stuck_thread
    assert engine.current_effect is None
    assert engine.stop_event.is_set() is True
    assert stuck_thread.join_timeouts == [2.0]


def test_close_does_not_release_keyboard_while_timed_out_worker_is_alive() -> None:
    class _ClosableKeyboard:
        def __init__(self) -> None:
            self.close_calls = 0

        def close(self) -> None:
            self.close_calls += 1

    engine = EffectsEngine()
    keyboard = _ClosableKeyboard()
    stuck_thread = _StuckEffectThread()
    engine.kb = keyboard  # type: ignore[assignment]
    engine.device_available = True
    engine.running = True
    engine.thread = stuck_thread  # type: ignore[assignment]

    engine.close()

    assert keyboard.close_calls == 0
    assert engine.kb is keyboard
    assert engine.device_available is True
    assert engine.stop_event.is_set() is True


def test_start_effect_restores_config_restart_brightness_before_thread_setup(monkeypatch) -> None:
    engine = EffectsEngine()
    engine.current_effect = "reactive_fade"
    engine._last_rendered_brightness = 40
    observed: list[int | None] = []

    monkeypatch.setattr(engine, "_ensure_device_available", lambda: True)
    monkeypatch.setattr(engine, "get_backend_effects", dict)
    monkeypatch.setattr(
        engine,
        "_start_sw_effect",
        lambda **_kwargs: observed.append(engine._last_rendered_brightness),
    )

    engine.start_effect("reactive_fade", preserve_last_rendered_brightness=True)

    assert observed == [40]


def test_get_backend_effects_returns_empty_dict_and_logs_backend_failures(caplog) -> None:
    class DummyBackend(_HardwareEffectsBackend):
        def effects(self):
            raise RuntimeError("effects boom")

    engine = EffectsEngine(backend=DummyBackend())

    with caplog.at_level(logging.ERROR, logger="src.core.effects.engine_core"):
        assert engine.get_backend_effects() == {}

    error_records = [record for record in caplog.records if "Failed to query backend effects" in record.getMessage()]
    assert error_records
    assert error_records[-1].exc_info is not None


def test_device_ensure_refreshes_dynamic_backend_capabilities() -> None:
    class DynamicBackend:
        color = False

        def capabilities(self) -> BackendCapabilities:
            return BackendCapabilities(
                brightness=True,
                per_key=False,
                color=self.color,
                hardware_effects=False,
                palette=False,
            )

    backend = DynamicBackend()
    engine = EffectsEngine(backend=backend)
    engine.device_available = True
    engine.kb = object()  # type: ignore[assignment]
    backend.color = True

    assert engine._ensure_device_available() is True
    assert engine.backend_caps.color is True


def test_get_backend_effects_propagates_unexpected_backend_failures() -> None:
    class DummyBackend(_HardwareEffectsBackend):
        def effects(self):
            raise AssertionError("unexpected effects bug")

    engine = EffectsEngine(backend=DummyBackend())

    with pytest.raises(AssertionError, match="unexpected effects bug"):
        engine.get_backend_effects()


def test_get_backend_colors_returns_empty_dict_and_logs_backend_failures(caplog) -> None:
    class DummyBackend(_HardwareEffectsBackend):
        def colors(self):
            raise RuntimeError("colors boom")

    engine = EffectsEngine(backend=DummyBackend())

    with caplog.at_level(logging.ERROR, logger="src.core.effects.engine_core"):
        assert engine.get_backend_colors() == {}

    error_records = [record for record in caplog.records if "Failed to query backend colors" in record.getMessage()]
    assert error_records
    assert error_records[-1].exc_info is not None


def test_get_backend_colors_propagates_unexpected_backend_failures() -> None:
    class DummyBackend(_HardwareEffectsBackend):
        def colors(self):
            raise AssertionError("unexpected colors bug")

    engine = EffectsEngine(backend=DummyBackend())

    with pytest.raises(AssertionError, match="unexpected colors bug"):
        engine.get_backend_colors()
