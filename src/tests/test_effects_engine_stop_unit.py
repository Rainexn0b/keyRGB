from __future__ import annotations

import time

from src.legacy.effects import EffectsEngine, _NullKeyboard


def test_start_effect_stops_previous_software_thread() -> None:
    engine = EffectsEngine()

    # Avoid touching real hardware.
    engine.kb = _NullKeyboard()
    engine.device_available = False
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]

    engine.start_effect("pulse", speed=0, brightness=25, color=(255, 0, 0))
    first_thread = engine.thread
    assert first_thread is not None

    # Immediately switch effects; the first thread must not keep running.
    engine.start_effect("fire", speed=0, brightness=25, color=(255, 0, 0))
    second_thread = engine.thread
    assert second_thread is not None
    assert second_thread is not first_thread

    # With stop_event-based waiting, the old thread should exit promptly.
    deadline = time.monotonic() + 0.5
    while first_thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.01)

    assert not first_thread.is_alive()

    engine.stop()


def test_static_effect_fades_between_colors() -> None:
    class SpyKeyboard(_NullKeyboard):
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
    engine.start_effect("static", speed=5, brightness=25, color=(0, 0, 255))

    # Fade should produce multiple intermediate frames and end at the target color.
    assert len(spy.calls) >= 2
    assert spy.calls[-1][0] == (0, 0, 255)

    def test_fade_to_non_black_never_writes_full_black() -> None:
        class SpyKeyboard(_NullKeyboard):
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
        for (rgb, _brightness) in spy.calls:
            assert rgb != (0, 0, 0)
