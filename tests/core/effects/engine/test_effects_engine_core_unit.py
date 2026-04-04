from __future__ import annotations

import logging

from src.core.effects.engine import EffectsEngine


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


def test_get_backend_effects_returns_empty_dict_and_logs_backend_failures(caplog) -> None:
    class DummyBackend:
        def effects(self):
            raise RuntimeError("effects boom")

    engine = EffectsEngine(backend=DummyBackend())

    with caplog.at_level(logging.ERROR, logger="src.core.effects.engine_core"):
        assert engine.get_backend_effects() == {}

    error_records = [record for record in caplog.records if "Failed to query backend effects" in record.getMessage()]
    assert error_records
    assert error_records[-1].exc_info is not None


def test_get_backend_colors_returns_empty_dict_and_logs_backend_failures(caplog) -> None:
    class DummyBackend:
        def colors(self):
            raise RuntimeError("colors boom")

    engine = EffectsEngine(backend=DummyBackend())

    with caplog.at_level(logging.ERROR, logger="src.core.effects.engine_core"):
        assert engine.get_backend_colors() == {}

    error_records = [record for record in caplog.records if "Failed to query backend colors" in record.getMessage()]
    assert error_records
    assert error_records[-1].exc_info is not None
