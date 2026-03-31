from __future__ import annotations

import time
from threading import Event

from src.core.effects.catalog import hardware_effect_selection_key
from src.core.effects.device import NullKeyboard
from src.core.effects.engine import EffectsEngine


def _effect_builder(effect_name: str, *, extra: tuple[str, ...] = ()):  # type: ignore[no-untyped-def]
    args = {"speed": None, "brightness": None}
    for key in extra:
        args[key] = None

    def build(**kwargs):
        _ = args
        return {"name": effect_name, **kwargs}

    return build


def test_start_effect_stops_previous_software_thread() -> None:
    engine = EffectsEngine()

    # Avoid touching real hardware.
    engine.kb = NullKeyboard()
    engine.device_available = False
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]

    engine.start_effect("rainbow_wave", speed=0, brightness=25, color=(255, 0, 0))
    first_thread = engine.thread
    assert first_thread is not None

    # Immediately switch effects; the first thread must not keep running.
    engine.start_effect("spectrum_cycle", speed=0, brightness=25, color=(255, 0, 0))
    second_thread = engine.thread
    assert second_thread is not None
    assert second_thread is not first_thread

    # With stop_event-based waiting, the old thread should exit promptly.
    deadline = time.monotonic() + 0.5
    while first_thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.01)

    assert not first_thread.is_alive()

    engine.stop()


def test_software_effect_fades_between_colors() -> None:
    class SpyKeyboard(NullKeyboard):
        def __init__(self):
            self.calls: list[tuple[tuple[int, int, int], int]] = []

        def set_color(self, color, *, brightness: int):
            r, g, b = color
            self.calls.append(((int(r), int(g), int(b)), int(brightness)))

    engine = EffectsEngine()

    spy = SpyKeyboard()
    engine.kb = spy
    engine.device_available = True
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]

    engine.current_color = (255, 0, 0)
    engine.start_effect("strobe", speed=5, brightness=25, color=(0, 0, 255))

    # Fade should produce multiple intermediate frames and include the target color.
    assert len(spy.calls) >= 2
    assert (0, 0, 255) in [rgb for (rgb, _b) in spy.calls]
    engine.stop()


def test_fade_to_non_black_never_writes_full_black() -> None:
    class SpyKeyboard(NullKeyboard):
        def __init__(self):
            self.calls: list[tuple[tuple[int, int, int], int]] = []

        def set_color(self, color, *, brightness: int):
            r, g, b = color
            self.calls.append(((int(r), int(g), int(b)), int(brightness)))

    engine = EffectsEngine()

    spy = SpyKeyboard()
    engine.kb = spy
    engine.device_available = True
    engine.brightness = 25

    engine._fade_uniform_color(
        from_color=(0, 0, 0),
        to_color=(255, 0, 0),
        brightness=25,
        duration_s=0.02,
        steps=8,
    )

    assert spy.calls
    for rgb, _brightness in spy.calls:
        assert rgb != (0, 0, 0)


def test_stop_resets_rendered_and_mode_brightness_caches() -> None:
    engine = EffectsEngine()
    engine._last_rendered_brightness = 25
    engine._last_hw_mode_brightness = 25

    engine.stop()

    assert engine._last_rendered_brightness is None
    assert engine._last_hw_mode_brightness is None


def test_start_hw_effect_uses_injected_backend_effects() -> None:
    class SpyKeyboard(NullKeyboard):
        def __init__(self):
            self.payloads: list[object] = []

        def set_effect(self, effect_data) -> None:
            self.payloads.append(effect_data)

    class DummyBackend:
        def effects(self):
            return {"snake": _effect_builder("snake", extra=("direction", "color"))}

        def colors(self):
            return {}

    engine = EffectsEngine(backend=DummyBackend())
    spy = SpyKeyboard()
    engine.kb = spy
    engine.device_available = True
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]
    engine.current_color = (9, 8, 7)
    engine.direction = "left"

    engine.start_effect("snake", speed=5, brightness=20, color=(9, 8, 7))

    assert spy.payloads
    payload = spy.payloads[-1]
    assert payload["name"] == "snake"
    assert payload["color"] == (9, 8, 7)
    assert payload["direction"] == "left"


def test_start_effect_rejects_legacy_generic_hw_name_without_backend_support() -> None:
    engine = EffectsEngine()
    engine.kb = NullKeyboard()
    engine.device_available = False
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]

    try:
        engine.start_effect("wave", speed=5, brightness=20, color=(9, 8, 7))
    except ValueError as exc:
        assert "Unknown effect: wave" in str(exc)
    else:
        raise AssertionError("Expected legacy generic hardware name to be rejected")


def test_start_effect_accepts_backend_exposed_hw_name() -> None:
    class SpyKeyboard(NullKeyboard):
        def __init__(self):
            self.payloads: list[object] = []

        def set_effect(self, effect_data) -> None:
            self.payloads.append(effect_data)

    class DummyBackend:
        def effects(self):
            return {"wave": _effect_builder("wave", extra=("color",))}

        def colors(self):
            return {}

    engine = EffectsEngine(backend=DummyBackend())
    spy = SpyKeyboard()
    engine.kb = spy
    engine.device_available = True
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]
    engine.current_color = (3, 2, 1)

    engine.start_effect("wave", speed=5, brightness=20, color=(3, 2, 1))

    assert spy.payloads
    payload = spy.payloads[-1]
    assert payload["name"] == "wave"
    assert payload["color"] == (3, 2, 1)


def test_start_effect_prefers_software_for_hw_sw_name_collision() -> None:
    class DummyBackend:
        def effects(self):
            return {"spectrum_cycle": _effect_builder("hw_spectrum_cycle")}

        def colors(self):
            return {}

    engine = EffectsEngine(backend=DummyBackend())
    engine.kb = NullKeyboard()
    engine.device_available = False
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]

    engine.start_effect("spectrum_cycle", speed=5, brightness=20, color=(3, 2, 1))

    assert engine.current_effect == "spectrum_cycle"

    engine.stop()


def test_start_effect_forced_hardware_collision_uses_backend_effect() -> None:
    class SpyKeyboard(NullKeyboard):
        def __init__(self):
            self.payloads: list[object] = []

        def set_effect(self, effect_data) -> None:
            self.payloads.append(effect_data)

    class DummyBackend:
        def effects(self):
            return {"spectrum_cycle": _effect_builder("spectrum_cycle")}

        def colors(self):
            return {}

    engine = EffectsEngine(backend=DummyBackend())
    spy = SpyKeyboard()
    engine.kb = spy
    engine.device_available = True
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]
    engine.current_color = (3, 2, 1)

    engine.start_effect(hardware_effect_selection_key("spectrum_cycle"), speed=5, brightness=20, color=(3, 2, 1))

    assert spy.payloads
    payload = spy.payloads[-1]
    assert payload["name"] == "spectrum_cycle"


def test_old_effect_thread_cannot_clear_new_thread_state() -> None:
    engine = EffectsEngine()

    engine.kb = NullKeyboard()
    engine.device_available = False
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]

    first_started = Event()
    first_release = Event()
    second_started = Event()

    def slow_first() -> None:
        first_started.set()
        while not first_release.is_set():
            time.sleep(0.01)

    def long_second() -> None:
        second_started.set()
        deadline = time.monotonic() + 0.4
        while time.monotonic() < deadline and engine.running and not engine.stop_event.is_set():
            time.sleep(0.01)

    engine._start_sw_effect(target=slow_first, prev_color=(0, 0, 0), fade_to_color=(255, 0, 0))
    first_thread = engine.thread
    assert first_thread is not None
    assert first_started.wait(timeout=0.2)

    engine._start_sw_effect(target=long_second, prev_color=(0, 0, 0), fade_to_color=(255, 0, 0))
    second_thread = engine.thread
    assert second_thread is not None
    assert second_thread is not first_thread
    assert second_started.wait(timeout=0.2)

    first_release.set()
    first_thread.join(timeout=1.0)
    assert not first_thread.is_alive()

    time.sleep(0.05)
    assert engine.running is True

    engine.stop()
